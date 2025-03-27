import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

class ServerHelper {
  final String serverUrl;
  late WebSocketChannel _channel;
  late StreamController _controller;

  ServerHelper({required this.serverUrl}) {
    _channel = WebSocketChannel.connect(Uri.parse(serverUrl));
    _controller = StreamController.broadcast(); // Make the stream broadcastable
    _controller.addStream(
        _channel.stream); // Add the original stream to the controller
  }

  // Expose the incoming message stream.
  Stream get messages => _controller.stream;

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

  void sendRawMessage(Map<String, dynamic> message) {
    print("Sending raw message: $message");
    _channel.sink.add(jsonEncode(message));
  }

  // Close the WebSocket connection
  void closeConnection() {
    _channel.sink.close(status.normalClosure);
    _controller.close(); // Close the controller when done
  }
}
