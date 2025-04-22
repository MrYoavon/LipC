class CallHistoryEntry {
  final String id;
  final String callerId;
  final String calleeId;
  final DateTime startedAt;
  final DateTime endedAt;
  CallType type;
  final Duration duration;
  final List<dynamic> transcripts;

  CallHistoryEntry({
    required this.id,
    required this.callerId,
    required this.calleeId,
    required this.startedAt,
    required this.endedAt,
    required this.type,
    required this.duration,
    required this.transcripts,
  });

  factory CallHistoryEntry.fromJson(Map<String, dynamic> json) {
    return CallHistoryEntry(
      id: json['_id'],
      callerId: json['caller_id'],
      calleeId: json['callee_id'],
      startedAt: DateTime.parse(json['started_at']),
      endedAt: DateTime.parse(json['ended_at']),
      type: CallType.unknown,
      duration: Duration(seconds: json['duration_seconds'].toInt()),
      transcripts: json['transcripts'] ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      '_id': id,
      'caller_id': callerId,
      'callee_id': calleeId,
      'started_at': startedAt.toIso8601String(),
      'ended_at': endedAt.toIso8601String(),
      'type': type.name,
      'duration': duration.inSeconds,
      'transcripts': transcripts,
    };
  }
}

enum CallType {
  incoming,
  outgoing,
  missed,
  unknown,
}
