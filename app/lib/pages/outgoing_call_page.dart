import 'package:flutter/material.dart';
import '../models/lip_c_user.dart';
import '../constants.dart';

class OutgoingCallPage extends StatelessWidget {
  final LipCUser remoteUser;

  const OutgoingCallPage({super.key, required this.remoteUser});

  Widget _buildProfileAvatar() {
    if (remoteUser.profilePic.isNotEmpty) {
      return CircleAvatar(
        radius: 80,
        backgroundImage: NetworkImage(remoteUser.profilePic),
        backgroundColor: Colors.transparent,
      );
    } else {
      // Generate initials from the remote user's name.
      String initials = remoteUser.name
          .split(" ")
          .map((e) => e.isNotEmpty ? e[0].toUpperCase() : '')
          .take(2)
          .join();
      return CircleAvatar(
        radius: 80,
        backgroundColor: AppColors().getUserColor(remoteUser.userId),
        child: Text(
          initials,
          style: const TextStyle(
            fontSize: 40,
            color: AppColors.background,
            fontWeight: FontWeight.bold,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop:
          false, // Prevents the user from going back to the previous screen yet allows us to use Navigator.pop(context).
      child: Scaffold(
        // No AppBar so that no back arrow is shown.
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [
                Color.fromARGB(255, 55, 159, 243),
                Color.fromARGB(255, 142, 181, 240),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          child: SafeArea(
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildProfileAvatar(),
                  const SizedBox(height: 30),
                  Text(
                    'Calling ${remoteUser.name}',
                    style: const TextStyle(
                      fontSize: 28,
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    '@${remoteUser.username}',
                    style: const TextStyle(
                      fontSize: 20,
                      color: Colors.white70,
                    ),
                  ),
                  const SizedBox(height: 40),
                  const CircularProgressIndicator(
                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    strokeWidth: 4,
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'Waiting for the user to answer...',
                    style: TextStyle(
                      fontSize: 16,
                      color: Colors.white70,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
