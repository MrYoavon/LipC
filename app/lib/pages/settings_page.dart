// lib/pages/settings_page.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../providers/model_preference_provider.dart';
import '../constants.dart';

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final model = ref.watch(modelPreferenceProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        backgroundColor: AppColors.background,
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
        children: [
          const Text(
            'Real-time inference model',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          RadioListTile<InferenceModel>(
            title: const Text('Lip-reading (video)'),
            value: InferenceModel.lip,
            groupValue: model,
            onChanged: (m) => ref.read(modelPreferenceProvider.notifier).setModel(m!),
          ),
          RadioListTile<InferenceModel>(
            title: const Text('Vosk speech-to-text (audio)'),
            value: InferenceModel.vosk,
            groupValue: model,
            onChanged: (m) => ref.read(modelPreferenceProvider.notifier).setModel(m!),
          ),
          const Divider(height: 32),
          ListTile(
            title: const Text('Clear cached preferences'),
            leading: const Icon(Icons.cleaning_services),
            onTap: () async {
              final prefs = await SharedPreferences.getInstance();
              await prefs.clear();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Preferences cleared')),
                );
              }
            },
          ),
        ],
      ),
    );
  }
}
