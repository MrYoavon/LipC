// lib/providers/contacts_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../models/lip_c_user.dart';
import '../helpers/server_helper.dart';
import '../helpers/app_logger.dart';
import 'server_helper_provider.dart';

/// Immutable state model for the contacts.
class ContactsState {
  final List<LipCUser> contacts;
  final bool isLoading;
  final String? errorMessage;

  ContactsState({
    this.contacts = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  ContactsState copyWith({
    List<LipCUser>? contacts,
    bool? isLoading,
    String? errorMessage,
  }) {
    return ContactsState(
      contacts: contacts ?? this.contacts,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage,
    );
  }
}

/// A StateNotifier that manages fetching/adding contacts via ServerHelper.
class ContactsNotifier extends StateNotifier<ContactsState> {
  final Logger _log = AppLogger.instance;
  final ServerHelper serverHelper;
  final String userId;

  ContactsNotifier({
    required this.serverHelper,
    required this.userId,
  }) : super(ContactsState()) {
    _log.i('📇 ContactsNotifier initialized for user: $userId');
  }

  /// Load all contacts from the server.
  Future<void> loadContacts() async {
    _log.i('📥 Loading contacts for user: $userId');
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final contactsListMap = await serverHelper.fetchContacts(userId);
      final fetchedContacts = contactsListMap.map(LipCUser.fromMap).toList();
      state = state.copyWith(contacts: fetchedContacts, isLoading: false);
      _log.i('✅ Loaded ${fetchedContacts.length} contacts for user: $userId');
    } catch (e, st) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
      _log.e('❌ Error loading contacts for user: $userId', error: e, stackTrace: st);
    }
  }

  /// Add a new contact on the server, then refresh.
  Future<void> addContact(String contactUsername) async {
    _log.i('➕ Adding contact "$contactUsername" for user: $userId');
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final response = await serverHelper.addContact(userId, contactUsername);
      if (response['success'] == true) {
        _log.i('✅ Successfully added contact "$contactUsername"');
        await loadContacts();
      } else {
        final errMsg = response['error_message'] ?? 'Failed to add contact';
        state = state.copyWith(
          isLoading: false,
          errorMessage: errMsg,
        );
        _log.w('⚠️ Failed to add contact "$contactUsername": $errMsg');
      }
    } catch (e, st) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
      _log.e('❌ Error adding contact "$contactUsername" for user: $userId', error: e, stackTrace: st);
    }
  }
}

/// A StateNotifierProvider for managing contacts per user.
final contactsProvider = StateNotifierProvider.family<ContactsNotifier, ContactsState, String>(
  (ref, userId) {
    final serverHelper = ref.watch(serverHelperProvider);
    final notifier = ContactsNotifier(
      serverHelper: serverHelper,
      userId: userId,
    );
    notifier.loadContacts();
    return notifier;
  },
);
