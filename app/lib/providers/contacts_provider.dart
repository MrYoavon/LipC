import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/lip_c_user.dart';
import '../helpers/server_helper.dart';
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
  final ServerHelper serverHelper;
  final String userId;

  ContactsNotifier({
    required this.serverHelper,
    required this.userId,
  }) : super(ContactsState());

  /// Load all contacts from the server.
  Future<void> loadContacts() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final contactsListMap = await serverHelper.fetchContacts(userId);
      final fetchedContacts = contactsListMap.map(LipCUser.fromMap).toList();
      state = state.copyWith(contacts: fetchedContacts, isLoading: false);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  /// Add a new contact on the server, then refresh.
  Future<void> addContact(String contactUsername) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final response = await serverHelper.addContact(userId, contactUsername);
      if (response["success"] == true) {
        // Refresh the list
        await loadContacts();
      } else {
        state = state.copyWith(
          isLoading: false,
          errorMessage: response["error_message"] ?? "Failed to add contact",
        );
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }
}

final contactsProvider = StateNotifierProvider.family<ContactsNotifier, ContactsState, String>(
  (ref, userId) {
    final serverHelper = ref.watch(serverHelperProvider);

    final notifier = ContactsNotifier(
      serverHelper: serverHelper,
      userId: userId,
    );
    // Load contacts immediately when the notifier is created:
    notifier.loadContacts();
    return notifier;
  },
);
