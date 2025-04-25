import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lip_c/widgets/server_connection_indicator.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
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
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final Logger _log = AppLogger.instance;
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _isLoading = false;
  bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    _log.i('💡 LoginPage mounted');
  }

  @override
  void dispose() {
    _log.i('🗑️ LoginPage disposed');
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  // Validator for username: checks for empty string and only allows alphanumeric characters and underscores.
  String? _validateUsername(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Username is required';
    }
    // This regex allows letters, numbers, and underscores.
    final validCharacters = RegExp(r'^[a-zA-Z0-9_]+$');
    if (!validCharacters.hasMatch(value.trim())) {
      return 'Username contains invalid characters';
    }
    return null;
  }

  // Validator for password: checks for empty string and a minimum length requirement.
  String? _validatePassword(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Password is required';
    }
    if (value.trim().length < 6) {
      return 'Password must be at least 6 characters long';
    }
    // Additional password validations can be added here.
    return null;
  }

  void _login() async {
    final username = _usernameController.text.trim();
    _log.i('🔑 Login attempt for user: $username');

    // Validate all form fields
    if (_formKey.currentState?.validate() ?? false) {
      setState(() => _isLoading = true);
      final password = _passwordController.text.trim();

      // Access the shared ServerHelper instance using ref.read
      final serverHelper = ref.read(serverHelperProvider);

      // Await a map response with "success" and "user_id"
      Map<String, dynamic> authResponse = await serverHelper.authenticate(username, password);
      _log.d('🛰️ Auth response: $authResponse');
      setState(() => _isLoading = false);
      print("Auth Response: $authResponse");

      if (authResponse["success"] == true) {
        final userId = authResponse["user_id"];
        _log.i('✅ Login succeeded for userId: $userId');
        final currentUser = LipCUser(
          userId: userId,
          username: username,
          name: authResponse["name"],
          profilePic: authResponse["profile_pic"],
        );
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
        _log.w('❌ Login failed: ${authResponse["error_message"]}');
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            SnackBar(
              content: Text(authResponse["error_message"] ?? "Invalid username or password"),
              backgroundColor: Colors.red,
            ),
          );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => FocusScope.of(context).unfocus(),
      child: ServerConnectionIndicator(
        child: Scaffold(
          backgroundColor: AppColors.background,
          body: Center(
            child: SingleChildScrollView(
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              padding: const EdgeInsets.symmetric(horizontal: 32.0, vertical: 24.0),
              child: Form(
                key: _formKey,
                child: Column(
                  children: [
                    const SizedBox(height: 40),

                    /// Logo at the top
                    Image.asset(
                      'assets/logo.png',
                      width: 80,
                      height: 80,
                      color: AppColors.accent,
                    ),
                    // const SizedBox(height: 20),

                    /// Welcome text
                    Text(
                      "Welcome to LipC",
                      style: GoogleFonts.fredoka(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppColors.accent,
                      ),
                    ),
                    const SizedBox(height: 40),

                    /// Username field
                    TextFormField(
                      controller: _usernameController,
                      maxLength: 20,
                      autocorrect: false,
                      enableSuggestions: false,
                      validator: _validateUsername,
                      decoration: InputDecoration(
                        labelText: "Username",
                        labelStyle: TextStyle(color: AppColors.textSecondary),
                        prefixIcon: Icon(Icons.person, color: AppColors.textSecondary),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderSide: BorderSide(color: AppColors.textSecondary, width: 2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),

                    /// Password field (with eye icon)
                    TextFormField(
                      controller: _passwordController,
                      maxLength: 128,
                      obscureText: _obscurePassword,
                      autocorrect: false,
                      enableSuggestions: false,
                      validator: _validatePassword,
                      decoration: InputDecoration(
                        labelText: "Password",
                        labelStyle: TextStyle(color: AppColors.textSecondary),
                        prefixIcon: Icon(Icons.lock, color: AppColors.textSecondary),
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscurePassword ? Icons.visibility_off : Icons.visibility,
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
                    const SizedBox(height: 12),

                    /// Gradient Login Button
                    SizedBox(
                      width: double.infinity,
                      height: 50,
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              const Color.fromARGB(255, 17, 37, 77),
                              AppColors.accent,
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
                            elevation: 0,
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
                    const SizedBox(height: 40),

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
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(builder: (context) => const RegisterPage()),
                            );
                          },
                          child: const Text("Sign Up"),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
