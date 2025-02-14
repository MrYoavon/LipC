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

  // Authenticate the user
  Future<bool> authenticate(String username, String password) async {
    final completer = Completer<bool>();

    _channel.sink.add(jsonEncode({
      "type": "authenticate",
      "username": username,
      "password": password,
    }));

    _controller.stream.listen((response) {
      final data = jsonDecode(response);
      if (data['type'] == 'authenticate') {
        completer.complete(data['success'] ?? false);
      }
    });

    return completer.future;
  }

  // Fetch the contacts list
  Future<List<Map<String, dynamic>>> fetchContacts() async {
    final completer = Completer<List<Map<String, dynamic>>>();

    _channel.sink.add(jsonEncode({"type": "fetch_contacts"}));

    _controller.stream.listen((response) {
      final data = jsonDecode(response);
      if (data['type'] == 'contacts') {
        completer.complete(List<Map<String, dynamic>>.from(data['data']));
      }
    });

    return completer.future;
  }

  // Close the WebSocket connection
  void closeConnection() {
    _channel.sink.close(status.normalClosure);
    _controller.close(); // Close the controller when done
  }
}
