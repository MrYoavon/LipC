import 'dart:convert';

class LipCUser {
  final String userId;
  final String username;
  final String name;
  final String profilePic;

  // Constructor
  LipCUser({
    required this.userId,
    required this.username,
    required this.name,
    required this.profilePic,
  });

  // Create a user from a Map (e.g., parsed JSON)
  factory LipCUser.fromMap(Map<String, dynamic> map) {
    return LipCUser(
      userId: map['_id'] ?? '',
      username: map['username'] ?? '',
      name: map['name'] ?? '',
      profilePic: map['profile_pic'] ?? '',
    );
  }

  // Convert a user to a Map (e.g., for sending JSON to the server)
  Map<String, dynamic> toMap() {
    return {
      '_id': userId,
      'username': username,
      'name': name,
      'profile_pic': profilePic,
    };
  }

  // (Optional) Create a user from JSON
  factory LipCUser.fromJson(String source) {
    final data = jsonDecode(source) as Map<String, dynamic>;
    return LipCUser.fromMap(data);
  }

  // (Optional) Convert a user to JSON
  String toJson() => jsonEncode(toMap());
}
