import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'package:uuid/uuid.dart';

import 'crypto_service.dart';
import 'jwt_service.dart';
import '../models/server_connection_status.dart';

class ServerHelper {
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
    print("Attempting to connect to $serverUrl");
    _channel = WebSocketChannel.connect(Uri.parse(serverUrl));
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
          Map<String, dynamic> payload = data['payload'];
          String serverPublicKey = payload['server_public_key'];
          String salt = payload['salt'];
          // Generate the client's key pair for the key exchange.
          await cryptoService.generateKeyPair();
          // Log and send the client's public key as a handshake response.
          print("Sending client public key: ${cryptoService.getPublicKey()}");
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
          print("Handshake complete. Ready to send encrypted messages.");
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
            print("Pong received at $_lastPongReceived");
          } else {
            // For non-pong messages, add the decrypted message to the stream for other handlers to process.
            _controller.add(decryptedText);
          }
        } catch (e) {
          // Log any errors encountered during decryption.
          print("Error decrypting message: $e");
        }
      }
    },
        // Callback when the WebSocket connection is closed.
        onDone: () {
      print("WebSocket closed.");
      _handleConnectionLoss();
    },
        // Callback when an error occurs on the WebSocket connection.
        onError: (error) {
      print("WebSocket error: $error");
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
    final Map<String, dynamic> message = {
      'message_id': Uuid().v4(),
      'timestamp': DateTime.now().toUtc().toIso8601String(),
      'msg_type': msgType,
      'success': success,
      'payload': payload ?? {}
    };

    if (!success) {
      message['error_code'] = errorCode ?? 'UNKNOWN_ERROR';
      message['error_message'] = errorMessage ?? 'An unknown error occurred.';
    }
    return message;
  }

  /// Encrypts a message and sends it over the WebSocket.
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
    if (msgType != 'authenticate' && msgType != 'signup' && msgType != 'ping') {
      // We don't want to add jwt token and userId to these messages
      // Ensure jwtTokenService and userId are set
      if (jwtTokenService == null || userId == null) {
        throw Exception("TokenService or userId is not set in ServerHelper.");
      }
      final String? accessToken = await jwtTokenService!.getAccessToken();
      if (accessToken == null) {
        throw Exception("Access token not available.");
      }

      // Add the JWT token and user ID to the message.
      message['jwt'] = accessToken;
      message['user_id'] = userId;
    }

    // Log the message being sent for debugging purposes.
    print("Sending message: $message");
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
      Duration(seconds: 10),
      (timer) {
        sendMessage(msgType: 'ping');
        // Compute the time elapsed since the last pong was received.
        final secondsSinceLastPong = DateTime.now().difference(_lastPongReceived).inSeconds;
        // If the elapsed time exceeds 15 seconds, assume the connection is lost.
        if (secondsSinceLastPong > 15) {
          print("No pong received within threshold ($secondsSinceLastPong seconds).");
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
    _countdownTimer = Timer.periodic(Duration(seconds: 1), (timer) {
      if (reconnectCountdown.value > 0) {
        reconnectCountdown.value--;
      } else {
        timer.cancel();
      }
    });

    print("Attempting to reconnect in $delaySeconds seconds...");
    // Schedule a reconnection attempt after the calculated delay.
    _reconnectTimer = Timer(Duration(seconds: delaySeconds), () {
      _countdownTimer?.cancel();
      _connect();
    });
  }

  /// Closes the WebSocket connection and cleans up resources.
  void closeConnection() {
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
  // Schedules a token refresh just before expiration.
  // --------------------------------------
  void scheduleTokenRefresh() async {
    // Get the current access token.
    final accessToken = await jwtTokenService!.getAccessToken();
    if (accessToken == null) return;

    // Determine the token's expiration time.
    DateTime expirationDate = JwtDecoder.getExpirationDate(accessToken);
    // For a safety margin, refresh 1 minute before actual expiry.
    final refreshDelay = expirationDate.difference(DateTime.now().toUtc()) - Duration(minutes: 1);

    // If the delay is negative, the token is already expired or about to expire.
    if (refreshDelay.isNegative) {
      // Refresh immediately.
      refreshAccessToken();
    } else {
      // Cancel any previous timer.
      _tokenRefreshTimer?.cancel();
      // Schedule the refresh.
      _tokenRefreshTimer = Timer(refreshDelay, refreshAccessToken);
      print("Scheduled token refresh in ${refreshDelay.inSeconds} seconds.");
    }
  }

  // --------------------------------------
  // Sends a refresh request to the server and updates the access token.
  // --------------------------------------
  Future<void> refreshAccessToken() async {
    final refreshToken = await jwtTokenService!.getRefreshToken();
    if (refreshToken == null) {
      throw Exception("Refresh token is missing.");
    }

    try {
      // Send refresh request.
      await sendMessage(
        msgType: 'refresh_token',
        payload: {'refresh_jwt': refreshToken},
      );

      // Wait for the server's refresh response message.
      final response = await messages.firstWhere((response) {
        final data = jsonDecode(response);
        return data['msg_type'] == 'refresh_token';
      }).timeout(Duration(seconds: 5), onTimeout: () {
        throw TimeoutException("Refresh token response timeout");
      });

      final data = jsonDecode(response);
      if (data['success'] == true) {
        // Extract the new access token from the response.
        final newAccessToken = data['payload']['access_token'];
        // Update storage while reusing the existing refresh token.
        await jwtTokenService!.saveTokens(newAccessToken, refreshToken);
        print("Access token refreshed successfully.");

        // Schedule the next token refresh based on the new token's expiration.
        scheduleTokenRefresh();
      } else {
        throw Exception("Token refresh failed: ${data['error_message']}");
      }
    } catch (e) {
      print("Error during token refresh: $e");
      // You might want to add additional error handling such as reauthentication.
    }
  }

  /// Authenticates the user by sending an encrypted authentication message with username and password.
  /// Awaits the server response and returns a map with the authentication result.
  Future<Map<String, dynamic>> authenticate(String username, String password) async {
    // Send an authentication request message.
    await sendMessage(
      msgType: 'authenticate',
      payload: {
        "username": username,
        "password": password,
      },
    );

    // Wait for the first response message of type 'authenticate'.
    final response = await messages.firstWhere((response) {
      final data = jsonDecode(response);
      return data['msg_type'] == 'authenticate';
    }).timeout(Duration(seconds: 5), onTimeout: () {
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

      // Return the user details on successful authentication.
      return {
        "success": true,
        "user_id": payload['user_id'],
        "name": payload['name'],
        "profile_pic": payload['profile_pic'],
        "access_token": payload['access_token'],
        "refresh_token": payload['refresh_token'],
      };
    } else {
      // Return error details if authentication fails.
      return {
        "success": false,
        "error_code": data['error_code'] ?? "UNKNOWN_ERROR",
        "error_message": data['error_message'] ?? "Authentication failed",
      };
    }
  }

  /// Registers a new user by sending an encrypted signup message with the provided user details.
  Future<Map<String, dynamic>> register(String username, String password, String name, String profilePic) async {
    // Send a signup request with user registration details.
    await sendMessage(
      msgType: 'signup',
      payload: {
        "username": username,
        "password": password,
        "name": name,
        "profile_pic": profilePic,
      },
    );

    // Wait for the signup response message.
    final response = await messages.firstWhere((response) {
      final data = jsonDecode(response);
      return data['msg_type'] == 'signup';
    });
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

      // Return the registered user ID on success.
      return {
        "success": true,
        "user_id": payload['user_id'],
        "access_token": payload['access_token'],
        "refresh_token": payload['refresh_token'],
      };
    } else {
      // Return error information if the signup process fails.
      return {
        "success": false,
        "error_code": data['error_code'] ?? "UNKNOWN_ERROR",
        "error_message": data['error_message'] ?? "Registration failed",
      };
    }
  }

  /// Fetches the list of contacts associated with a particular user.
  Future<List<Map<String, dynamic>>> fetchContacts(String userId) async {
    // Send an encrypted request to get contacts for the given user ID.
    await sendMessage(
      msgType: 'get_contacts',
      payload: {
        "user_id": userId,
      },
    );

    // Wait for the response message that contains the contacts list.
    final response = await messages.firstWhere((response) {
      final data = jsonDecode(response);
      return data['msg_type'] == 'get_contacts';
    });

    // Parse and return the contacts list.
    final data = jsonDecode(response);
    if (data['success'] == false) {
      // If the response indicates failure, return an empty list.
      return [];
    }
    final payload = data['payload'];
    return List<Map<String, dynamic>>.from(payload['contacts']);
  }

  /// Adds a new contact for the user.
  Future<Map<String, dynamic>> addContact(String userId, String contactName) async {
    // Send an encrypted request to add a contact using the user's ID and the contact's username.
    await sendMessage(
      msgType: 'add_contact',
      payload: {
        "user_id": userId,
        "contact_username": contactName,
      },
    );

    // Wait for the response message corresponding to adding a contact.
    final response = await messages.firstWhere((response) {
      final data = jsonDecode(response);
      return data["msg_type"] == "add_contact";
    });
    // Parse and return the response.
    final data = jsonDecode(response);
    return data;
  }
}
