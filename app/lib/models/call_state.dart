// lib/models/call_state.dart
import 'lip_c_user.dart';

enum CallStatus { idle, calling, inCall, ended, rejected }

class CallState {
  final CallStatus status;
  final LipCUser? remoteUser;

  const CallState({this.status = CallStatus.idle, this.remoteUser});

  CallState copyWith({CallStatus? status, LipCUser? remoteUser}) {
    return CallState(
      status: status ?? this.status,
      remoteUser: remoteUser ?? this.remoteUser,
    );
  }
}
