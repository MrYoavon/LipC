import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lip_c/widgets/server_connection_indicator.dart';

import '../models/lip_c_user.dart';
import '../providers/contacts_provider.dart';
import '../providers/current_user_provider.dart';
import '../providers/server_helper_provider.dart';
import 'contacts_page.dart';
import '../constants.dart';
import 'register_page.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  _LoginPageState createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _isLoading = false;
  bool _obscurePassword = true; // Toggle for showing/hiding password

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _login() async {
    setState(() => _isLoading = true);
    final username = _usernameController.text.trim();
    final password = _passwordController.text.trim();

    // Access the shared ServerHelper instance using ref.read
    final serverHelper = ref.read(serverHelperProvider);

    // Await a map response with "success" and "user_id"
    Map<String, dynamic> authResponse =
        await serverHelper.authenticate(username, password);
    setState(() => _isLoading = false);

    if (authResponse["success"] == true) {
      final currentUser = LipCUser(
          userId: authResponse["user_id"],
          username: username,
          name: authResponse["name"],
          profilePic: authResponse["profile_pic"]);
      ref.read(currentUserProvider.notifier).setUser(currentUser);

      // Load the contacts list for the current user
      ref.read(contactsProvider(currentUser.userId).notifier).loadContacts();

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (context) => ContactsPage(),
        ),
      );
    } else {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content:
                Text(authResponse["reason"] ?? "Invalid username or password"),
            backgroundColor: Colors.red,
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ServerConnectionIndicator(
      child: Scaffold(
        backgroundColor: AppColors.background,
        body: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32.0),
            child: Column(
              children: [
                const SizedBox(height: 240),

                /// Logo at the top
                Image.asset(
                  'assets/logo.png',
                  width: 80,
                  height: 80,
                  color: AppColors.accent,
                ),
                const SizedBox(height: 20),

                /// Welcome text
                Text(
                  "Welcome to LipC",
                  style: GoogleFonts.fredoka(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: AppColors.accent,
                  ),
                ),
                const SizedBox(height: 20),

                /// Username field
                TextField(
                  controller: _usernameController,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: InputDecoration(
                    labelText: "Username",
                    labelStyle: TextStyle(color: AppColors.textSecondary),
                    prefixIcon:
                        Icon(Icons.person, color: AppColors.textSecondary),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide:
                          BorderSide(color: AppColors.textSecondary, width: 2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
                const SizedBox(height: 15),

                /// Password field (with eye icon)
                TextField(
                  controller: _passwordController,
                  obscureText: _obscurePassword,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: InputDecoration(
                    labelText: "Password",
                    labelStyle: TextStyle(color: AppColors.textSecondary),
                    prefixIcon:
                        Icon(Icons.lock, color: AppColors.textSecondary),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscurePassword
                            ? Icons.visibility_off
                            : Icons.visibility,
                        color: AppColors.textSecondary,
                      ),
                      onPressed: () {
                        setState(() {
                          _obscurePassword = !_obscurePassword;
                        });
                      },
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: AppColors.accent, width: 2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
                const SizedBox(height: 20),

                /// Gradient Login Button
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          const Color.fromARGB(
                              255, 17, 37, 77), // Lighter berry
                          AppColors.accent, // Deeper berry
                        ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _login,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.transparent,
                        disabledBackgroundColor: Colors.transparent,
                        shadowColor: Colors.transparent,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        elevation: 0, // Let the gradient stand out
                      ),
                      child: _isLoading
                          ? const CircularProgressIndicator(color: Colors.white)
                          : const Text(
                              "Login",
                              style: TextStyle(
                                fontSize: 16,
                                color: Colors.white,
                              ),
                            ),
                    ),
                  ),
                ),
                const SizedBox(height: 220),

                /// Don't have an account? Sign Up
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text("Not a member?"),
                    TextButton(
                        style: TextButton.styleFrom(
                          padding: const EdgeInsets.only(left: 0),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        onPressed: () {
                          // Navigate to the registration page
                          Navigator.pushReplacement(
                            context,
                            MaterialPageRoute(
                                builder: (context) => const RegisterPage()),
                          );
                        },
                        child: const Text("Sign Up")),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
