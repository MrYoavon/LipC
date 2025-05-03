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

  // controllers
  final TextEditingController _firstNameController = TextEditingController();
  final TextEditingController _lastNameController = TextEditingController();
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmPasswordController = TextEditingController();

  bool _isLoading = false;
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;

  // password rule trackers
  bool _isPassword8 = false;
  bool _hasUppercase = false;
  bool _hasLowercase = false;
  bool _hasNumber = false;
  bool _hasSymbol = false;

  @override
  void initState() {
    super.initState();
    _log.i('💡 RegisterPage mounted');
    _passwordController.addListener(_validatePassword);
  }

  @override
  void dispose() {
    _log.i('🗑️ RegisterPage disposed');
    _firstNameController.dispose();
    _lastNameController.dispose();
    _usernameController.dispose();
    _passwordController.removeListener(_validatePassword);
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  // Live‐validate the password rules
  void _validatePassword() {
    final pw = _passwordController.text;
    setState(() {
      _isPassword8 = pw.length >= 8;
      _hasUppercase = pw.contains(RegExp(r'[A-Z]'));
      _hasLowercase = pw.contains(RegExp(r'[a-z]'));
      _hasNumber = pw.contains(RegExp(r'\d'));
      _hasSymbol = pw.contains(RegExp(r'[!@#\$%^&*(),.?":{}|<>]'));
    });
  }

  // Reusable widget for each rule
  Widget _buildPasswordRule({required bool passed, required String label}) {
    return Row(
      children: [
        Icon(
          passed ? Icons.check_circle : Icons.cancel,
          color: passed ? Colors.green : Colors.red,
          size: 18,
        ),
        const SizedBox(width: 8),
        Text(label, style: TextStyle(color: passed ? Colors.green : Colors.red)),
      ],
    );
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

  String? _validatePasswordField(String? value) {
    if (value == null || value.isEmpty) {
      return 'Password is required';
    }
    final passwordRegex = RegExp(r'^(?=.{8,}$)' // at least 8 characters long
        r'(?=.*[a-z])' // at least one lowercase
        r'(?=.*[A-Z])' // at least one uppercase
        r'(?=.*\d)' // at least one digit
        r'(?=.*[!@#\$%^&*(),.?":{}|<>])' // at least one special
        r'.*$');
    if (!passwordRegex.hasMatch(value)) {
      return 'Password must be ≥8 characters long and include uppercase, lowercase, number, and special character';
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

      final serverHelper = ref.read(serverHelperProvider);
      setState(() => _isLoading = true);

      Map<String, dynamic> registrationResponse = await serverHelper.register(
        username,
        password,
        fullName,
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
                              counterText: '',
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
                              counterText: '',
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
                    const SizedBox(height: 16),

                    // Username field
                    TextFormField(
                      controller: _usernameController,
                      maxLength: 20,
                      decoration: InputDecoration(
                        labelText: "Username",
                        labelStyle: TextStyle(color: AppColors.textSecondary),
                        prefixIcon: Icon(Icons.alternate_email, color: AppColors.textSecondary),
                        counterText: '',
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
                    const SizedBox(height: 16),

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
                        counterText: '',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderSide: BorderSide(color: AppColors.accent, width: 2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      validator: _validatePasswordField,
                    ),
                    const SizedBox(height: 16),

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
                        counterText: '',
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

                    // Live password‐rule feedback
                    _buildPasswordRule(passed: _isPassword8, label: 'At least 8 characters'),
                    _buildPasswordRule(passed: _hasUppercase, label: '1 uppercase letter'),
                    _buildPasswordRule(passed: _hasLowercase, label: '1 lowercase letter'),
                    _buildPasswordRule(passed: _hasNumber, label: '1 number'),
                    _buildPasswordRule(passed: _hasSymbol, label: '1 special character'),

                    const SizedBox(height: 24),
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
