import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../helpers/call_orchestrator.dart';
import '../helpers/call_history_service.dart';
import '../widgets/server_connection_indicator.dart';
import '../constants.dart';
import '../providers/current_user_provider.dart';
import '../providers/server_helper_provider.dart';
import '../providers/contacts_provider.dart';
import 'call_history_page.dart';
import 'login_page.dart';

class ContactsPage extends ConsumerStatefulWidget {
  const ContactsPage({super.key});

  @override
  _ContactsPageState createState() => _ContactsPageState();
}

class _ContactsPageState extends ConsumerState<ContactsPage> {
  final Logger _log = AppLogger.instance;

  bool _isSearching = false;
  String _searchQuery = '';
  final FocusNode _searchFocusNode = FocusNode();

  late CallOrchestrator callOrchestrator;
  late CallHistoryService callHistoryService;

  @override
  void initState() {
    super.initState();
    _log.i('💡 ContactsPage mounted');

    final serverHelper = ref.read(serverHelperProvider);
    final currentUser = ref.read(currentUserProvider)!;
    final contacts = ref.read(contactsProvider(currentUser.userId)).contacts;

    _log.d('Initializing CallOrchestrator for user ${currentUser.username}');
    callOrchestrator = CallOrchestrator(
      context: context,
      localUser: currentUser,
      serverHelper: serverHelper,
      contacts: contacts,
    );

    _log.d('Initializing CallHistoryService');
    callHistoryService = CallHistoryService(serverHelper: serverHelper);
  }

  @override
  void dispose() {
    _log.i('🗑️ ContactsPage disposed');
    _searchFocusNode.dispose();
    super.dispose();
  }

  void _onSearchTap() {
    setState(() => _isSearching = !_isSearching);
    _log.i('🔍 Search mode toggled: $_isSearching');
  }

  void _onTapOutside() {
    if (_isSearching && _searchQuery.isEmpty) {
      setState(() => _isSearching = false);
      _log.i('🔍 Search mode exited (empty query)');
    }
  }

  String _getInitials(String name) {
    List<String> nameParts = name.split(" ");
    String initials = '';
    for (var part in nameParts) {
      if (part.isNotEmpty) initials += part[0].toUpperCase();
    }
    return initials.length > 2 ? initials.substring(0, 2) : initials;
  }

  void _showAddContactDialog() {
    _log.i('➕ Showing Add Contact dialog');
    final TextEditingController _contactNameController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text("Add Contact", style: TextStyle(fontWeight: FontWeight.bold)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text("Enter the username of the contact you wish to add:",
                  style: TextStyle(fontSize: 14, color: Colors.black54)),
              const SizedBox(height: 16),
              TextField(
                controller: _contactNameController,
                decoration: InputDecoration(
                  hintText: "Contact username",
                  prefixIcon: const Icon(Icons.person),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppColors.accent, width: 2),
                  ),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                _log.i('✖️ Add Contact cancelled');
                Navigator.pop(context);
              },
              child: const Text("Cancel"),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: () async {
                final contactName = _contactNameController.text.trim();
                final currentUser = ref.read(currentUserProvider)!;
                final contactsState = ref.read(contactsProvider(currentUser.userId));
                final contactsNotifier = ref.read(contactsProvider(currentUser.userId).notifier);

                if (contactName.isEmpty) {
                  _log.w('⚠️ Attempted to add empty contact');
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Please enter a username")),
                  );
                  return;
                }
                if (contactName == currentUser.username) {
                  _log.w('⚠️ Attempted to add self as contact');
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("You cannot add yourself")),
                  );
                  return;
                }
                if (contactsState.contacts.any((c) => c.username == contactName)) {
                  _log.w('⚠️ Attempted to add existing contact: $contactName');
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Contact already exists")),
                  );
                  return;
                }

                Navigator.pop(context);
                _log.i('➕ Adding new contact: $contactName');
                await contactsNotifier.addContact(contactName);
              },
              child: const Text("Add"),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final currentUser = ref.watch(currentUserProvider)!;

    ref.listen<ContactsState>(
      contactsProvider(currentUser.userId),
      (previous, next) {
        if (next.errorMessage?.isNotEmpty == true) {
          _log.e('❌ Contacts error: ${next.errorMessage}');
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              backgroundColor: Colors.red,
              content: Text(next.errorMessage!),
              duration: const Duration(seconds: 3),
            ),
          );
        }
        _log.d('📇 Contacts updated: ${next.contacts.length}');
        callOrchestrator.updateContacts(next.contacts);
      },
    );

    final contactsState = ref.watch(contactsProvider(currentUser.userId));
    final contacts = contactsState.contacts;
    final isLoading = contactsState.isLoading;

    return ServerConnectionIndicator(
      child: GestureDetector(
        onTap: _onTapOutside,
        child: Scaffold(
          appBar: AppBar(
            backgroundColor: AppColors.background,
            leading: IconButton(
              icon: const Icon(Icons.search),
              onPressed: _onSearchTap,
              padding: const EdgeInsets.only(left: 16),
            ),
            title: _isSearching
                ? TextField(
                    focusNode: _searchFocusNode,
                    onChanged: (query) {
                      setState(() => _searchQuery = query);
                      _log.d('🔍 Search query: $_searchQuery');
                    },
                    autofocus: true,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      hintText: 'Search contacts...',
                      hintStyle: TextStyle(color: AppColors.textPrimary),
                      border: InputBorder.none,
                    ),
                  )
                : const Center(
                    child: Text('Lip-C', style: TextStyle(color: AppColors.textPrimary)),
                  ),
            actions: [
              PopupMenuButton<String>(
                onSelected: (value) async {
                  if (value == "logout") {
                    _log.i('🔒 User selected logout');
                    final serverHelper = ref.read(serverHelperProvider);
                    await serverHelper.jwtTokenService?.clearTokens();
                    ref.read(currentUserProvider.notifier).clearUser();
                    if (!mounted) return;
                    Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute(builder: (_) => const LoginPage()),
                      (route) => false,
                    );
                  }
                },
                itemBuilder: (context) => [
                  const PopupMenuItem<String>(value: 'settings', child: Text('Settings')),
                  const PopupMenuDivider(),
                  const PopupMenuItem<String>(
                    value: 'logout',
                    child: Text('Logout', style: TextStyle(color: Colors.red)),
                  ),
                ],
                icon: CircleAvatar(
                  backgroundImage:
                      currentUser.profilePic.isNotEmpty ? AssetImage(currentUser.profilePic) as ImageProvider : null,
                  backgroundColor: AppColors.accent,
                  foregroundColor: AppColors.background,
                  child: currentUser.profilePic.isEmpty
                      ? Text(
                          _getInitials(currentUser.username),
                          style: const TextStyle(color: AppColors.background, fontSize: 20),
                        )
                      : null,
                ),
                padding: const EdgeInsets.only(right: 16),
              ),
            ],
          ),
          body: isLoading
              ? const Center(child: CircularProgressIndicator())
              : contacts.isEmpty
                  ? const Center(child: Text("No contacts found."))
                  : Stack(
                      children: [
                        ListView.builder(
                          itemCount: contacts.length,
                          itemBuilder: (context, index) {
                            final contact = contacts[index];
                            final color = AppColors().getUserColor(contact.userId);

                            if (_searchQuery.isNotEmpty &&
                                !contact.name.toLowerCase().contains(_searchQuery.toLowerCase()) &&
                                !contact.username.toLowerCase().contains(_searchQuery.toLowerCase())) {
                              return const SizedBox.shrink();
                            }

                            return ListTile(
                              leading: CircleAvatar(
                                backgroundColor: color,
                                foregroundColor: AppColors.background,
                                child: Text(contact.name[0]),
                              ),
                              title: Row(
                                children: [
                                  Text(contact.name),
                                  Text(" @${contact.username}",
                                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                                ],
                              ),
                              subtitle: const Text('Status: Online'),
                              trailing: IconButton(
                                icon: const Icon(Icons.video_call),
                                onPressed: () {
                                  _log.i('📞 Calling user: ${contact.username}');
                                  callOrchestrator.callUser(contact);
                                },
                              ),
                            );
                          },
                        ),
                        Positioned(
                          bottom: 24,
                          right: 24,
                          child: FloatingActionButton(
                            backgroundColor: AppColors.accent,
                            foregroundColor: AppColors.background,
                            onPressed: _showAddContactDialog,
                            tooltip: 'Add Contact',
                            heroTag: 'add_contact',
                            child: const Icon(Icons.add),
                          ),
                        ),
                        Positioned(
                          bottom: 24,
                          left: 24,
                          child: FloatingActionButton(
                            backgroundColor: AppColors.accent,
                            foregroundColor: AppColors.background,
                            onPressed: () {
                              _log.i('📜 Opening call history');
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (context) => CallHistoryPage(
                                    service: callHistoryService,
                                    userId: currentUser.userId,
                                  ),
                                ),
                              );
                            },
                            tooltip: 'Call History',
                            heroTag: 'call_history',
                            child: const Icon(Icons.history),
                          ),
                        ),
                      ],
                    ),
        ),
      ),
    );
  }
}
