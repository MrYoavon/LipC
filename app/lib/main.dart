import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'constants.dart';
import 'helpers/app_logger.dart';
import 'helpers/riverpod_logger.dart';
import 'pages/startup_page.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppLogger.init();

  runApp(
    ProviderScope(
      observers: [RiverpodLogger()],
      child: LipC(),
    ),
  );
}

class LipC extends StatelessWidget {
  const LipC({super.key});

  // This widget is the root of your application.
  @override
  Widget build(BuildContext context) {
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
    return MaterialApp(
      title: 'Lip-C',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          secondary: AppColors.accent,
        ),
        scaffoldBackgroundColor: AppColors.background,
        textTheme: const TextTheme(
          displayLarge: TextStyle(
            fontSize: 57.0,
            fontWeight: FontWeight.w400,
            letterSpacing: -0.25,
            color: AppColors.textPrimary,
          ),
          headlineLarge: TextStyle(
            fontSize: 32.0,
            fontWeight: FontWeight.w400,
            color: AppColors.textPrimary,
          ),
          titleMedium: TextStyle(
            fontSize: 16.0,
            fontWeight: FontWeight.w500,
            color: AppColors.textPrimary,
          ),
          bodyMedium: TextStyle(
            fontSize: 14.0,
            fontWeight: FontWeight.w400,
            color: AppColors.textPrimary,
          ),
        ),
      ),
      home: const StartupPage(),
    );
  }
}
