class LipCUser {
  final String userId;
  final String username;
  final String name;

  // Constructor
  LipCUser({
    required this.userId,
    required this.username,
    required this.name,
  });

  // Create a user from a Map (e.g., parsed JSON)
  factory LipCUser.fromMap(Map<String, dynamic> map) {
    return LipCUser(
      userId: map['_id'] ?? '',
      username: map['username'] ?? '',
      name: map['name'] ?? '',
    );
  }

  // Convert a user to a Map (e.g., for sending JSON to the server)
  Map<String, dynamic> toMap() {
    return {
      '_id': userId,
      'username': username,
      'name': name,
    };
  }
}
