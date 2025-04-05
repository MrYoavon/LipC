import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

import '../models/server_connection_status.dart';

class ServerHelper {
  final String serverUrl;
  late WebSocketChannel _channel;
  late StreamController _controller;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  Timer? _countdownTimer;
  bool _isConnected = false;
  int _reconnectAttempts = 0;
  DateTime _lastPongReceived = DateTime.now();

  final _connectionStatusController =
      StreamController<ServerConnectionStatus>.broadcast();
  Stream<ServerConnectionStatus> get connectionStatus =>
      _connectionStatusController.stream;

  // Expose a ValueNotifier for the countdown (in seconds)
  ValueNotifier<int> reconnectCountdown = ValueNotifier<int>(0);

  ServerHelper({required this.serverUrl}) {
    _connect();
  }

  // Establish a connection and set up listeners.
  void _connect() {
    print("Attempting to connect to $serverUrl");
    _channel = WebSocketChannel.connect(Uri.parse(serverUrl));
    _controller = StreamController.broadcast();
    _lastPongReceived = DateTime.now();

    // Listen to incoming messages.
    _channel.stream.listen((message) {
      try {
        final data = jsonDecode(message);
        if (data['type'] == 'pong') {
          _lastPongReceived = DateTime.now();
          _reconnectAttempts =
              0; // Reset reconnection attempts on a successful connection.
          print("Pong received at $_lastPongReceived");
        }
      } catch (e) {
        // Handle parsing errors if needed.
      }
      _controller.add(message);
    }, onDone: () {
      print("WebSocket closed.");
      _handleConnectionLoss();
    }, onError: (error) {
      print("WebSocket error: $error");
      _handleConnectionLoss();
    });

    _isConnected = true;
    _connectionStatusController.add(
        ServerConnectionStatus.connected); // Inform UI that we are connected.
    startHeartbeat();
  }

  // Expose the incoming message stream.
  Stream get messages => _controller.stream;

  void sendRawMessage(Map<String, dynamic> message) {
    print("Sending raw message: $message");
    _channel.sink.add(jsonEncode(message));
  }

  // Start a periodic heartbeat that sends a ping and checks for pong response.
  void startHeartbeat() {
    _heartbeatTimer = Timer.periodic(Duration(seconds: 10), (timer) {
      // Send a ping message.
      sendRawMessage({'type': 'ping'});

      // Check if the last pong was received too long ago.
      final secondsSinceLastPong =
          DateTime.now().difference(_lastPongReceived).inSeconds;
      if (secondsSinceLastPong > 15) {
        print(
            "No pong received within threshold ($secondsSinceLastPong seconds).");
        // Optionally, close or attempt to reconnect.
        closeConnection();
      }
    });
  }

  // Stop the heartbeat timer.
  void stopHeartbeat() {
    _heartbeatTimer?.cancel();
  }

  // Listen for incoming pong messages.
  void listenForPong() {
    _controller.stream.listen((message) {
      final data = jsonDecode(message);
      if (data['type'] == 'pong') {
        _lastPongReceived = DateTime.now();
        print("Pong received at $_lastPongReceived");
      }
    });
  }

  // Handle connection loss by cleaning up and scheduling a reconnect.
  void _handleConnectionLoss() {
    if (!_isConnected) return; // Already handling disconnection.
    _isConnected = false;
    stopHeartbeat();
    // Close the existing channel and controller.
    _channel.sink.close(status.normalClosure);
    _controller.close();
    // Inform UI that the app is attempting to reconnect.
    _connectionStatusController.add(ServerConnectionStatus.reconnecting);
    _attemptReconnect();
  }

  // Attempt to reconnect with an exponential backoff delay.
  void _attemptReconnect() {
    _reconnectAttempts++;
    final delaySeconds =
        (2 * _reconnectAttempts).clamp(2, 64); // Exponential backoff delay.
    reconnectCountdown.value = delaySeconds; // Set initial countdown value.

    _countdownTimer?.cancel();
    _countdownTimer = Timer.periodic(
      Duration(seconds: 1),
      (timer) {
        if (reconnectCountdown.value > 0) {
          reconnectCountdown.value--;
        } else {
          timer.cancel();
        }
      },
    );

    print("Attempting to reconnect in $delaySeconds seconds...");
    _reconnectTimer = Timer(Duration(seconds: delaySeconds), () {
      _countdownTimer?.cancel();
      _connect();
    });
  }

  // Close the connection manually.
  void closeConnection() {
    stopHeartbeat();
    _reconnectTimer?.cancel();
    _countdownTimer?.cancel();
    _channel.sink.close(status.normalClosure);
    _controller.close();
    _isConnected = false;
    // Inform UI that we're now disconnected.
    _connectionStatusController.add(ServerConnectionStatus.disconnected);
  }

  // Authenticate the user
  Future<Map<String, dynamic>> authenticate(
      String username, String password) async {
    _channel.sink.add(jsonEncode({
      "type": "authenticate",
      "username": username,
      "password": password,
    }));

    final response = await _controller.stream.firstWhere((response) {
      final data = jsonDecode(response);
      return data['type'] == 'authenticate';
    }).timeout(Duration(seconds: 5), onTimeout: () {
      // Update connection status to timeout so UI can react.
      _connectionStatusController.add(ServerConnectionStatus.timeout);
      throw TimeoutException("Server response timeout");
    });
    final data = jsonDecode(response);
    if (data['success'] == true && data.containsKey('user_id')) {
      return {
        "success": true,
        "user_id": data['user_id'],
        "name": data['name'],
        "profile_pic": data['profile_pic'],
      };
    } else {
      return {
        "success": false,
        "reason": data['reason'] ?? "Invalid username or password",
      };
    }
  }

  // Register a new user
  // Returns a map with success true and the user_id if registration succeeded,
  // or success false and a reason if it failed.
  Future<Map<String, dynamic>> register(
      String username, String password, String name, String profilePic) async {
    // Send registration request.
    _channel.sink.add(jsonEncode({
      "type": "signup",
      "username": username,
      "password": password,
      "name": name,
      "profile_pic": profilePic,
    }));

    // Wait for the first response with type 'signup'.
    final response = await _controller.stream.firstWhere((response) {
      final data = jsonDecode(response);
      return data['type'] == 'signup';
    });
    final data = jsonDecode(response);

    if (data['success'] == true && data.containsKey('user_id')) {
      // Registration succeeded, return the user_id.
      return {
        "success": true,
        "user_id": data['user_id'],
      };
    } else {
      // Registration failed; return an error reason.
      return {
        "success": false,
        "reason": data['reason'] ?? "Registration failed",
      };
    }
  }

  // Fetch the contacts list for a given user.
  Future<List<Map<String, dynamic>>> fetchContacts(String userId) async {
    // Send a request for contacts, including the user_id.
    _channel.sink.add(jsonEncode({
      "type": "get_contacts",
      "user_id": userId,
    }));

    // Wait for the first response with type "get_contacts".
    final response = await _controller.stream.firstWhere((response) {
      final data = jsonDecode(response);
      return data['type'] == 'get_contacts';
    });

    final data = jsonDecode(response);
    return List<Map<String, dynamic>>.from(data['contacts']);
  }

  // Add a contact for a given user by the contact's name.
  Future<Map<String, dynamic>> addContact(
      String userId, String contactName) async {
    _channel.sink.add(jsonEncode({
      "type": "add_contact",
      "user_id": userId,
      "contact_username": contactName,
    }));

    // Wait for the first response with type "add_contact"
    final response = await _controller.stream.firstWhere((response) {
      final data = jsonDecode(response);
      return data['type'] == 'add_contact';
    });
    final data = jsonDecode(response);
    return data;
  }
}
