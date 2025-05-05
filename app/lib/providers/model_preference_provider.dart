// model_preference_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lip_c/helpers/server_helper.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'server_helper_provider.dart';

enum InferenceModel { vosk, lip }

class ModelPreferenceNotifier extends StateNotifier<InferenceModel> {
  ModelPreferenceNotifier(this._serverHelper) : super(InferenceModel.lip) {
    _load();
  }
  final ServerHelper _serverHelper;

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString('inference_model');
    if (stored != null) {
      state = InferenceModel.values.firstWhere((e) => e.name == stored, orElse: () => InferenceModel.lip);
    }

    // Tell the server
    await _serverHelper.sendModelPreference(state);
  }

  Future<void> setModel(InferenceModel model) async {
    state = model;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('inference_model', model.name);
    // Tell the server
    await _serverHelper.sendModelPreference(state);
  }
}

final modelPreferenceProvider = StateNotifierProvider<ModelPreferenceNotifier, InferenceModel>((ref) {
  final serverHelper = ref.read(serverHelperProvider);
  return ModelPreferenceNotifier(serverHelper);
});
