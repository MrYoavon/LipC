class CallHistoryEntry {
  final String id;
  final String contactName;
  final String contactId;
  final DateTime timestamp;
  final CallType type; // incoming, outgoing, missed
  final Duration duration;

  CallHistoryEntry({
    required this.id,
    required this.contactName,
    required this.contactId,
    required this.timestamp,
    required this.type,
    required this.duration,
  });

  factory CallHistoryEntry.fromJson(Map<String, dynamic> json) {
    return CallHistoryEntry(
      id: json['_id'],
      contactName: json['contactName'],
      contactId: json['contactId'],
      timestamp: DateTime.parse(json['timestamp']),
      type: CallType.values.byName(json['type']),
      duration: Duration(seconds: json['durationSeconds']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      '_id': id,
      'contactName': contactName,
      'contactId': contactId,
      'timestamp': timestamp.toIso8601String(),
      'type': type.name,
      'durationSeconds': duration.inSeconds,
    };
  }
}

enum CallType {
  incoming,
  outgoing,
  missed,
}
