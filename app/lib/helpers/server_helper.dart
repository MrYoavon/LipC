import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import 'package:logger/logger.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'package:uuid/uuid.dart';

import '../providers/model_preference_provider.dart';
import 'app_logger.dart';
import 'crypto_service.dart';
import 'jwt_service.dart';
import '../models/server_connection_status.dart';

class ServerHelper {
  final Logger _log = AppLogger.instance;

  // -------------------------------------------------------------
  // Server connection and dependency instance variables
  // -------------------------------------------------------------
  final String serverUrl;
  late WebSocketChannel _channel;
  final CryptoService cryptoService; // CryptoService instance for key management.
  JWTTokenService? jwtTokenService; // JWTTokenService instance for token management.
  String? userId; // User ID for the authenticated user. Should be set after login.

  // -------------------------------------------------------------
  // Stream controllers and notifiers for message handling & connection status
  // -------------------------------------------------------------
  late StreamController<String> _controller; // Broadcast controller for decrypted messages.
  Stream<String> get messages => _controller.stream; // Exposes a stream of decrypted messages.

  final _connectionStatusController =
      StreamController<ServerConnectionStatus>.broadcast(); // Broadcast connection status.
  Stream<ServerConnectionStatus> get connectionStatus =>
      _connectionStatusController.stream; // Exposes connection status updates.

  ValueNotifier<int> reconnectCountdown = ValueNotifier<int>(0); // Countdown (in seconds) for reconnect UI.

  // -------------------------------------------------------------
  // Timer variables for heartbeat and reconnection
  // -------------------------------------------------------------
  Timer? _heartbeatTimer; // Timer for sending periodic heartbeat pings.
  Timer? _reconnectTimer; // Timer for scheduling reconnection attempts.
  Timer? _countdownTimer; // Timer to update the reconnect countdown every second.
  Timer? _tokenRefreshTimer; // Timer for scheduling token refresh

  // -------------------------------------------------------------
  // Connection state variables and handshake status
  // -------------------------------------------------------------
  bool _isConnected = false; // Flag indicating if the connection is active.
  int _reconnectAttempts = 0; // Number of reconnection attempts made.
  DateTime _lastPongReceived = DateTime.now(); // Timestamp of the last received pong.
  bool handshakeComplete = false; // Flag for handshake (ECDH & AES) completion.

  ServerHelper({required this.serverUrl, required this.cryptoService}) {
    _connect();
  }

  /// Establishes the WebSocket connection to the server and sets up listeners.
  void _connect() {
    _log.i('🔗 Attempting to connect to $serverUrl');
    final client = HttpClient()
      ..badCertificateCallback =
          (X509Certificate cert, String host, int port) => true; // Accept all certificates for development.
    _channel = IOWebSocketChannel.connect(
      serverUrl,
      customClient: client,
    );
    // Initialize the stream controller for broadcasting messages.
    _controller = StreamController<String>.broadcast();
    // Reset the last pong received time.
    _lastPongReceived = DateTime.now();

    // Listen for incoming messages on the WebSocket.
    _channel.stream.listen((encryptedMessage) async {
      // Process handshake messages until the handshake is complete.
      if (!handshakeComplete) {
        final data = jsonDecode(encryptedMessage);
        // If the message type is 'handshake', then process the key exchange.
        if (data['msg_type'] == 'handshake') {
          _log.i('🤝 Received handshake from server');
          final Map<String, dynamic> payload = data['payload'];
          final String serverPublicKey = payload['server_public_key'];
          final String salt = payload['salt'];
          // Generate the client's key pair for the key exchange.
          await cryptoService.generateKeyPair();
          // Log and send the client's public key as a handshake response.
          _log.d('🔐 Sending client public key: ${cryptoService.getPublicKey()}');
          final handshakeResponse = createStructuredMessage(
            msgType: 'handshake',
            payload: {'client_public_key': cryptoService.getPublicKey()},
          );

          _channel.sink.add(jsonEncode(handshakeResponse));
          // Compute the shared secret and derive the AES key using the server's public key and the provided salt.
          await cryptoService.computeSharedSecret(
            serverPublicKey,
            utf8.encode(salt),
          );
          // Mark handshake as complete so that subsequent messages are handled as encrypted messages.
          handshakeComplete = true;
          _log.i('✅ Handshake complete; ready for encrypted messaging');
          // Exit early to avoid processing further logic until handshake is finalized.
          return;
        }
      } else {
        // If handshake is complete, process incoming encrypted messages.
        try {
          final Map<String, dynamic> encryptedData = jsonDecode(encryptedMessage);
          final decryptedText = await cryptoService.decryptMessage(encryptedData);
          // Parse the decrypted text as JSON.
          final decryptedData = jsonDecode(decryptedText);
          // If the decrypted message is a 'pong', update the last pong time.
          if (decryptedData['msg_type'] == 'pong') {
            _lastPongReceived = DateTime.now();
            // Reset reconnection attempts upon successful pong reception (confirms connection has been fully established).
            _reconnectAttempts = 0;
          } else {
            // For non-pong messages, add the decrypted message to the stream for other handlers to process.
            _log.d('📩 Received message: $decryptedData');
            _controller.add(decryptedText);
          }
        } catch (e) {
          // Log any errors encountered during decryption.
          _log.e('❌ Error decrypting message', error: e);
        }
      }
    },
        // Callback when the WebSocket connection is closed.
        onDone: () {
      _log.w('⚠️ WebSocket closed by server');
      _handleConnectionLoss();
    },
        // Callback when an error occurs on the WebSocket connection.
        onError: (error) {
      _log.e('❌ WebSocket error', error: error);
      _handleConnectionLoss();
    });

    // Mark the connection as active.
    _isConnected = true;
    // Notify listeners that the connection is established.
    _connectionStatusController.add(ServerConnectionStatus.connected);
    // Start sending periodic heartbeat messages.
    startHeartbeat();
  }

  Map<String, dynamic> createStructuredMessage({
    required String msgType,
    Map<String, dynamic>? payload,
    bool success = true,
    String? errorCode,
    String? errorMessage,
  }) {
    final Map<String, dynamic> message = <String, dynamic>{
      'message_id': Uuid().v4(),
      'timestamp': DateTime.now().toUtc().toIso8601String(),
      'msg_type': msgType,
      'success': success,
      'payload': payload ?? {},
    };

    if (!success) {
      message['error_code'] = errorCode ?? 'UNKNOWN_ERROR';
      message['error_message'] = errorMessage ?? 'An unknown error occurred.';
    }
    return message;
  }

  /// Encrypts and sends a structured message over the WebSocket.
  Future<void> sendMessage({
    required String msgType,
    Map<String, dynamic> payload = const {},
    bool success = true,
    String? errorCode,
    String? errorMessage,
  }) async {
    // Create a structured message with the provided message type and additional data.
    final message = createStructuredMessage(
      msgType: msgType,
      payload: payload,
      success: success,
      errorCode: errorCode,
      errorMessage: errorMessage,
    );

    // Check if msgType is different from 'authenticate', 'signup' or 'ping'
    if (!['authenticate', 'signup', 'ping', 'refresh_token'].contains(msgType)) {
      // We don't want to add jwt token and userId to these messages
      // Ensure jwtTokenService and userId are set
      if (jwtTokenService == null || userId == null) {
        throw Exception("TokenService or userId is not set in ServerHelper.");
      }
      final accessToken = await jwtTokenService!.getAccessToken();
      if (accessToken == null) {
        throw Exception("Access token not available.");
      }

      // Add the JWT token and user ID to the message.
      message['jwt'] = accessToken;
      message['user_id'] = userId;
    }

    _log.d('📤 Sending message: $message');
    // Serialize the message map into a JSON string.
    final plaintext = jsonEncode(message);
    // Encrypt the plaintext message using the crypto service.
    final encryptedPayload = await cryptoService.encryptMessage(plaintext);
    // Send the encrypted payload (encoded as JSON) over the WebSocket.
    _channel.sink.add(jsonEncode(encryptedPayload));
  }

  /// Initiates a periodic heartbeat to keep the connection alive and monitor its health.
  /// It sends an encrypted 'ping' every 10 seconds and checks if a 'pong' response is received within 15 seconds.
  void startHeartbeat() {
    _heartbeatTimer = Timer.periodic(
      const Duration(seconds: 10),
      (timer) {
        sendMessage(msgType: 'ping');
        // Compute the time elapsed since the last pong was received.
        final secondsSinceLastPong = DateTime.now().difference(_lastPongReceived).inSeconds;
        // If the elapsed time exceeds 15 seconds, assume the connection is lost.
        if (secondsSinceLastPong > 15) {
          _log.w('⌛ No pong for $secondsSinceLastPong seconds; closing connection.');
          closeConnection();
        }
      },
    );
  }

  /// Stops the heartbeat timer.
  void stopHeartbeat() {
    _heartbeatTimer?.cancel();
  }

  /// Handles connection loss by cleaning up resources and initiating a reconnection attempt.
  void _handleConnectionLoss() {
    // If already marked as disconnected, do nothing.
    if (!_isConnected) return;
    _log.w('🔄 Handling connection loss; will attempt reconnect');
    _isConnected = false;
    // Stop the heartbeat ping.
    stopHeartbeat();
    // Close the WebSocket connection with a normal closure status.
    _channel.sink.close(status.normalClosure);
    // Close the message stream controller.
    _controller.close();
    // Notify listeners that the connection is being reestablished.
    _connectionStatusController.add(ServerConnectionStatus.reconnecting);
    // Reset handshake flag since a new connection is required.
    handshakeComplete = false;
    // Begin the reconnection process.
    _attemptReconnect();
  }

  /// Attempts to reconnect to the server using an exponential backoff strategy.
  void _attemptReconnect() {
    // Increment reconnection attempts.
    _reconnectAttempts++;
    // Calculate delay for the reconnection attempt, clamped between 2 and 64 seconds.
    final delaySeconds = (2 * _reconnectAttempts).clamp(2, 64);
    // Set the countdown for UI updates.
    reconnectCountdown.value = delaySeconds;

    // Cancel any existing countdown timer.
    _countdownTimer?.cancel();
    // Start a countdown timer to update the reconnect countdown every second.
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (reconnectCountdown.value > 0) {
        reconnectCountdown.value--;
      } else {
        timer.cancel();
      }
    });

    _log.i('🔁 Attempting to reconnect in $delaySeconds seconds');
    // Schedule a reconnection attempt after the calculated delay.
    _reconnectTimer = Timer(Duration(seconds: delaySeconds), () {
      _countdownTimer?.cancel();
      _connect();
    });
  }

  /// Closes the WebSocket and notifies listeners.
  void closeConnection() {
    _log.i('✖️ Closing connection');
    // Stop the heartbeat ping.
    stopHeartbeat();
    // Cancel any pending reconnection timers.
    _reconnectTimer?.cancel();
    _countdownTimer?.cancel();
    // Close the WebSocket connection with a normal closure status.
    _channel.sink.close(status.normalClosure);
    // Close the message stream controller.
    _controller.close();
    // Mark the connection as inactive and notify listeners.
    _isConnected = false;
    _connectionStatusController.add(ServerConnectionStatus.disconnected);
  }

  // --------------------------------------
  // Schedules a token refresh one minute before expiry.
  // --------------------------------------
  void scheduleTokenRefresh() async {
    // Get the current access token.
    final accessToken = await jwtTokenService?.getAccessToken();
    if (accessToken == null) return;

    // Determine the token's expiration time.
    final DateTime expirationDate = JwtDecoder.getExpirationDate(accessToken);
    // For a safety margin, refresh 1 minute before actual expiry.
    final refreshDelay = expirationDate.difference(DateTime.now().toUtc()) - const Duration(minutes: 1);

    // If the delay is negative, the token is already expired or about to expire.
    if (refreshDelay.isNegative) {
      // Refresh immediately.
      refreshAccessToken();
    } else {
      // Cancel any previous timer.
      _tokenRefreshTimer?.cancel();
      // Schedule the refresh.
      _tokenRefreshTimer = Timer(refreshDelay, refreshAccessToken);
      _log.d('⏱️ Scheduled token refresh in ${refreshDelay.inSeconds}s');
    }
  }

  // --------------------------------------
  // Sends a refresh request to the server and updates the access token.
  // --------------------------------------
  Future<void> refreshAccessToken() async {
    final refreshToken = await jwtTokenService?.getRefreshToken();
    if (refreshToken == null) throw Exception("Refresh token is missing.");

    try {
      // Send refresh request.
      await sendMessage(msgType: 'refresh_token', payload: {'refresh_jwt': refreshToken});

      // Wait for the server's refresh response message.
      final response = await messages
          .firstWhere(
        (msg) => jsonDecode(msg)['msg_type'] == 'refresh_token',
      )
          .timeout(const Duration(seconds: 5), onTimeout: () {
        throw TimeoutException("Refresh token response timeout");
      });

      final data = jsonDecode(response);
      if (data['success'] == true) {
        // Extract the new access token from the response.
        final newAccessToken = data['payload']['access_token'];
        // Update storage while reusing the existing refresh token.
        await jwtTokenService!.saveTokens(newAccessToken, refreshToken);
        _log.i('🔄 Access token refreshed');

        // Schedule the next token refresh based on the new token's expiration.
        scheduleTokenRefresh();
      } else {
        throw Exception("Token refresh failed: ${data['error_message']}");
      }
    } catch (e) {
      _log.e('❌ Error during token refresh', error: e);
      // You might want to add additional error handling such as reauthentication.
    }
  }

  /// Authenticates the user by sending an encrypted authentication message with username and password.
  /// Awaits the server response and returns a map with the authentication result.
  Future<Map<String, dynamic>> authenticate(String username, String password) async {
    try {
      // Send an authentication request message.
      await sendMessage(
        msgType: 'authenticate',
        payload: {"username": username, "password": password},
      );

      // Wait for the first response message of type 'authenticate'.
      final response = await messages
          .firstWhere(
        (msg) => jsonDecode(msg)['msg_type'] == 'authenticate',
      )
          .timeout(const Duration(seconds: 5), onTimeout: () {
        // If no authentication response is received within 5 seconds, update connection status and throw a timeout exception.
        _connectionStatusController.add(ServerConnectionStatus.timeout);
        throw TimeoutException("Server response timeout");
      });

      // Parse the authentication response.
      final data = jsonDecode(response);
      final payload = data['payload'];
      if (data['success'] == true && payload.containsKey('user_id')) {
        final accessToken = payload["access_token"];
        final refreshToken = payload["refresh_token"];

        // Set the userId in ServerHelper.
        userId = payload['user_id'];

        // Initialize jwtTokenService if not already set.
        jwtTokenService ??= JWTTokenService();

        // Save the tokens locally via JWTTokenService.
        await jwtTokenService!.saveTokens(accessToken, refreshToken);

        // Start scheduling token refresh.
        scheduleTokenRefresh();

        _log.i('✅ Authentication succeeded for $username');

        // Return the user details on successful authentication.
        return {
          "success": true,
          "user_id": payload['user_id'],
          "name": payload['name'],
          "access_token": payload['access_token'],
          "refresh_token": payload['refresh_token'],
        };
      } else {
        _log.w('❌ Authentication failed: ${data['error_message']}');
        // Return error details if authentication fails.
        return {
          "success": false,
          "error_code": data['error_code'] ?? "UNKNOWN_ERROR",
          "error_message": data['error_message'] ?? "Authentication failed",
        };
      }
    } on TimeoutException {
      return {
        "success": false,
        "error_code": "TIMEOUT",
        "error_message": "Server did not respond in time",
      };
    } on StateError {
      // Stream closed before any matching element
      _connectionStatusController.add(ServerConnectionStatus.disconnected);
      return {
        "success": false,
        "error_code": "STATE_ERROR",
        "error_message": "Connection was closed before login could complete",
      };
    } catch (e) {
      return {
        "success": false,
        "error_code": "UNKNOWN_ERROR",
        "error_message": "An unknown error occurred: $e",
      };
    }
  }

  /// Registers a new user by sending an encrypted signup message with the provided user details.
  Future<Map<String, dynamic>> register(
    String username,
    String password,
    String name,
  ) async {
    try {
      // Send a signup request with user registration details.
      await sendMessage(
        msgType: 'signup',
        payload: {
          "username": username,
          "password": password,
          "name": name,
        },
      );

      // Wait for the signup response message.
      final response = await messages.firstWhere(
        (msg) => jsonDecode(msg)['msg_type'] == 'signup',
      );
      // Parse the signup response.
      final data = jsonDecode(response);
      final payload = data['payload'];
      if (data['success'] == true && payload.containsKey('user_id')) {
        final accessToken = payload["access_token"];
        final refreshToken = payload["refresh_token"];

        // Set the userId in ServerHelper.
        userId = payload['user_id'];

        // Initialize jwtTokenService if not already set.
        jwtTokenService ??= JWTTokenService();

        // Save the tokens locally via JWTTokenService.
        await jwtTokenService!.saveTokens(accessToken, refreshToken);

        // Start scheduling token refresh.
        scheduleTokenRefresh();

        _log.i('✅ Registration succeeded for $username');

        // Return the registered user ID on success.
        return {
          "success": true,
          "user_id": payload['user_id'],
          "access_token": payload['access_token'],
          "refresh_token": payload['refresh_token'],
        };
      } else {
        _log.w('❌ Registration failed: ${data['error_message']}');
        // Return error information if the signup process fails.
        return {
          "success": false,
          "error_code": data['error_code'] ?? "UNKNOWN_ERROR",
          "error_message": data['error_message'] ?? "Registration failed",
        };
      }
    } on TimeoutException {
      return {
        "success": false,
        "error_code": "TIMEOUT",
        "error_message": "Server did not respond in time",
      };
    } on StateError {
      // Stream closed before any matching element
      _connectionStatusController.add(ServerConnectionStatus.disconnected);
      return {
        "success": false,
        "error_code": "STATE_ERROR",
        "error_message": "Connection was closed before registration could complete",
      };
    } catch (e) {
      return {
        "success": false,
        "error_code": "UNKNOWN_ERROR",
        "error_message": "An unknown error occurred: $e",
      };
    }
  }

  /// Attempts auto-login via stored refresh token.
  Future<Map<String, dynamic>> tryAutoLogin() async {
    // jwtTokenService is created the first time you call authenticate/register,
    // but on a cold start it’s still null → create it now.
    jwtTokenService ??= JWTTokenService();

    final refreshToken = await jwtTokenService!.getRefreshToken();
    _log.i('🔄 Trying auto-login with refresh token: $refreshToken');
    if (refreshToken == null) {
      return {"success": false, "reason": "NO_REFRESH_TOKEN"};
    }

    // Send the same message the LoginPage would trigger.
    await sendMessage(msgType: 'refresh_token', payload: {'refresh_jwt': refreshToken});

    // Wait for the server’s answer (same pattern as in refreshAccessToken()).
    final response = await messages
        .firstWhere(
      (msg) => jsonDecode(msg)['msg_type'] == 'refresh_token',
    )
        .timeout(const Duration(seconds: 5), onTimeout: () {
      throw TimeoutException("Refresh token response timeout");
    });

    final data = jsonDecode(response);

    if (data['success'] == true) {
      final newAccess = data['payload']['access_token'];
      // Keep the SAME refresh token, per your server design.
      await jwtTokenService!.saveTokens(newAccess, refreshToken);
      userId = data['payload']['user_id']; // so subsequent calls attach it
      // Re-schedule automatic refresh
      scheduleTokenRefresh();

      _log.i('✅ Auto-login succeeded for ${data['payload']['username']}');

      return {
        "success": true,
        "user_id": data['payload']['user_id'],
        "username": data['payload']['username'],
        "name": data['payload']['name'],
        "access_token": newAccess,
        "refresh_token": refreshToken,
      };
    }

    // Refresh token was expired / revoked
    await jwtTokenService!.clearTokens();
    _log.w('⚠️ Auto-login failed: ${data['error_message']}');
    return {
      "success": false,
      "reason": data['error_code'] ?? "EXPIRED",
      "error_message": data['error_message'],
    };
  }

  /// Log out the user by clearing the stored tokens and closing the connection.
  /// This method also sends a logout message to the server.
  Future<void> logout() async {
    // Send a logout message to the server.
    await sendMessage(msgType: 'logout', payload: {"user_id": userId});

    // Clear the stored tokens.
    await jwtTokenService?.clearTokens();

    userId = null; // Reset the user ID.
  }

  /// Fetches the list of contacts for the given user.
  Future<List<Map<String, dynamic>>> fetchContacts(String userId) async {
    // Send an encrypted request to get contacts for the given user ID.
    await sendMessage(msgType: 'get_contacts', payload: {"user_id": userId});

    // Wait for the response message that contains the contacts list.
    final response = await messages.firstWhere(
      (msg) => jsonDecode(msg)['msg_type'] == 'get_contacts',
    );

    // Parse and return the contacts list.
    final data = jsonDecode(response);
    if (data['success'] == false) {
      _log.w('⚠️ fetchContacts failed for $userId');
      // If the response indicates failure, return an empty list.
      return [];
    }
    _log.i('📇 fetchContacts returned ${data['payload']['contacts'].length} entries');
    return List<Map<String, dynamic>>.from(data['payload']['contacts']);
  }

  /// Adds a contact and returns the server response.
  Future<Map<String, dynamic>> addContact(String userId, String contactName) async {
    // Send an encrypted request to add a contact using the user's ID and the contact's username.
    await sendMessage(msgType: 'add_contact', payload: {"user_id": userId, "contact_username": contactName});

    // Wait for the response message corresponding to adding a contact.
    final response = await messages.firstWhere(
      (msg) => jsonDecode(msg)['msg_type'] == 'add_contact',
    );
    // Parse and return the response.
    final data = jsonDecode(response);
    if (data['success'] == true) {
      _log.i('➕ addContact succeeded: $contactName added for $userId');
    } else {
      _log.w('⚠️ addContact failed: ${data['error_message']}');
    }
    return data;
  }

  Future<void> sendModelPreference(InferenceModel model) async {
    final access = await jwtTokenService?.getAccessToken();
    if (access == null) return;
    // Send a message to the server to set the model preference.
    await sendMessage(
      msgType: 'set_model_preference',
      payload: {"model_type": model.name}, // "lip" | "vosk"
    );
    _log.d('📡 Sent model preference: ${model.name}');
  }
}
