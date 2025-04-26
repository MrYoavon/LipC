import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../models/lip_c_user.dart';
import '../providers/contacts_provider.dart';
import '../providers/current_user_provider.dart';
import '../providers/model_preference_provider.dart';
import '../providers/server_helper_provider.dart';
import '../constants.dart';
import '../widgets/server_connection_indicator.dart';
import 'contacts_page.dart';
import 'login_page.dart';

class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({super.key});

  @override
  _RegisterPageState createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  final Logger _log = AppLogger.instance;

  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();

  final TextEditingController _firstNameController = TextEditingController();
  final TextEditingController _lastNameController = TextEditingController();
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmPasswordController = TextEditingController();
  final TextEditingController _profilePicController = TextEditingController();

  bool _isLoading = false;
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;

  @override
  void initState() {
    super.initState();
    _log.i('💡 RegisterPage mounted');
  }

  @override
  void dispose() {
    _log.i('🗑️ RegisterPage disposed');
    _firstNameController.dispose();
    _lastNameController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _profilePicController.dispose();
    super.dispose();
  }

  // Validator that ensures the name contains only English letters.
  String? _validateName(String? value, String fieldName) {
    if (value == null || value.trim().isEmpty) {
      return '$fieldName is required';
    }
    final RegExp validName = RegExp(r'^[A-Za-z]+$');
    if (!validName.hasMatch(value.trim())) {
      return '$fieldName must only contain English letters';
    }
    return null;
  }

  String? _validateUsername(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Username is required';
    }
    // Allow only alphanumeric characters and underscores.
    final validCharacters = RegExp(r'^[a-zA-Z0-9_]+$');
    if (!validCharacters.hasMatch(value.trim())) {
      return 'Username contains invalid characters';
    }
    return null;
  }

  String? _validatePassword(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Password is required';
    }
    if (value.trim().length < 6) {
      return 'Password must be at least 6 characters long';
    }
    return null;
  }

  String? _validateConfirmPassword(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Confirm your password';
    }
    if (value.trim() != _passwordController.text.trim()) {
      return 'Passwords do not match';
    }
    return null;
  }

  void _register() async {
    final username = _usernameController.text.trim();
    _log.i('📝 Register attempt for user: $username');

    if (_formKey.currentState?.validate() ?? false) {
      final firstName = _firstNameController.text.trim();
      final lastName = _lastNameController.text.trim();
      final fullName = '$firstName $lastName';
      final password = _passwordController.text.trim();
      final profilePic = _profilePicController.text.trim();

      final serverHelper = ref.read(serverHelperProvider);
      setState(() => _isLoading = true);

      Map<String, dynamic> registrationResponse = await serverHelper.register(
        username,
        password,
        fullName,
        profilePic,
      );
      _log.d('🛰️ Registration response: $registrationResponse');
      setState(() => _isLoading = false);

      if (registrationResponse["success"] == true) {
        final userId = registrationResponse["user_id"];
        _log.i('✅ Registration succeeded for userId: $userId');

        final currentUser = LipCUser(
          userId: userId,
          username: username,
          name: fullName,
          profilePic: profilePic,
        );
        ref.read(currentUserProvider.notifier).setUser(currentUser);

        // Load the contacts list for the current user
        ref.read(contactsProvider(currentUser.userId).notifier).loadContacts();

        // Send the model preference to the server
        final InferenceModel modelPreference = ref.read(modelPreferenceProvider);
        await serverHelper.sendModelPreference(modelPreference);

        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (context) => ContactsPage(),
          ),
        );
      } else {
        _log.w('❌ Registration failed: ${registrationResponse["error_message"]}');
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            SnackBar(
              content: Text(
                registrationResponse["error_message"] ?? "Registration failed. Username might be taken.",
              ),
              backgroundColor: Colors.red,
            ),
          );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => FocusScope.of(context).unfocus(), // Dismiss the keyboard
      child: ServerConnectionIndicator(
        child: Scaffold(
          backgroundColor: AppColors.background,
          body: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 32.0),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const SizedBox(height: 40),

                    // Logo at the top
                    Image.asset(
                      'assets/logo.png',
                      width: 80,
                      height: 80,
                      color: AppColors.accent,
                    ),
                    const SizedBox(height: 20),

                    // Header Text
                    Text(
                      "Create Your Account",
                      style: GoogleFonts.fredoka(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppColors.accent,
                      ),
                    ),
                    const SizedBox(height: 20),

                    // First Name & Last Name side by side
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _firstNameController,
                            maxLength: 30,
                            decoration: InputDecoration(
                              labelText: "First Name",
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
                            validator: (value) => _validateName(value, "First name"),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _lastNameController,
                            maxLength: 30,
                            decoration: InputDecoration(
                              labelText: "Last Name",
                              labelStyle: TextStyle(color: AppColors.textSecondary),
                              prefixIcon: Icon(Icons.person_outline, color: AppColors.textSecondary),
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderSide: BorderSide(color: AppColors.textSecondary, width: 2),
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                            validator: (value) => _validateName(value, "Last name"),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),

                    // Username field
                    TextFormField(
                      controller: _usernameController,
                      maxLength: 20,
                      decoration: InputDecoration(
                        labelText: "Username",
                        labelStyle: TextStyle(color: AppColors.textSecondary),
                        prefixIcon: Icon(Icons.alternate_email, color: AppColors.textSecondary),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderSide: BorderSide(color: AppColors.textSecondary, width: 2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      validator: _validateUsername,
                    ),
                    const SizedBox(height: 12),

                    // Password field
                    TextFormField(
                      controller: _passwordController,
                      maxLength: 128,
                      obscureText: _obscurePassword,
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
                      validator: _validatePassword,
                    ),
                    const SizedBox(height: 12),

                    // Confirm Password field
                    TextFormField(
                      controller: _confirmPasswordController,
                      maxLength: 128,
                      obscureText: _obscureConfirmPassword,
                      decoration: InputDecoration(
                        labelText: "Confirm Password",
                        labelStyle: TextStyle(color: AppColors.textSecondary),
                        prefixIcon: Icon(Icons.lock_outline, color: AppColors.textSecondary),
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscureConfirmPassword ? Icons.visibility_off : Icons.visibility,
                            color: AppColors.textSecondary,
                          ),
                          onPressed: () {
                            setState(() {
                              _obscureConfirmPassword = !_obscureConfirmPassword;
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
                      validator: _validateConfirmPassword,
                    ),
                    const SizedBox(height: 12),

                    // Gradient Register Button
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
                          onPressed: _isLoading ? null : _register,
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
                                  "Sign Up",
                                  style: TextStyle(
                                    fontSize: 16,
                                    color: Colors.white,
                                  ),
                                ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 40),

                    // Link to login page
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text("Already have an account?"),
                        TextButton(
                          style: TextButton.styleFrom(
                            padding: const EdgeInsets.only(left: 0),
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          ),
                          onPressed: () {
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(builder: (context) => const LoginPage()),
                            );
                          },
                          child: const Text("Login"),
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
