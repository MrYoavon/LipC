import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lip_c/widgets/server_connection_indicator.dart';

import '../constants.dart';
import '../helpers/call_orchestrator.dart';
import '../helpers/call_history_service.dart';
import '../providers/current_user_provider.dart';
import '../providers/server_helper_provider.dart';
import '../providers/contacts_provider.dart';
import 'call_history_page.dart';

class ContactsPage extends ConsumerStatefulWidget {
  const ContactsPage({super.key});

  @override
  _ContactsPageState createState() => _ContactsPageState();
}

class _ContactsPageState extends ConsumerState<ContactsPage> {
  bool _isSearching = false;
  String _searchQuery = '';
  final FocusNode _searchFocusNode = FocusNode();

  late CallOrchestrator callOrchestrator;
  late CallHistoryService callHistoryService;

  @override
  void initState() {
    super.initState();

    final serverHelper = ref.read(serverHelperProvider);
    final currentUser = ref.read(currentUserProvider)!;
    final contacts = ref.read(contactsProvider(currentUser.userId)).contacts;

    setState(() {
      callOrchestrator = CallOrchestrator(
        context: context,
        localUser: currentUser,
        serverHelper: serverHelper,
        contacts: contacts,
      );
      callHistoryService = CallHistoryService(serverHelper: serverHelper);
    });
  }

  @override
  void dispose() {
    _searchFocusNode.dispose();
    super.dispose();
  }

  void _onSearchTap() {
    setState(() {
      _isSearching = !_isSearching;
    });
  }

  void _onTapOutside() {
    if (_isSearching && _searchQuery.isEmpty) {
      setState(() {
        _isSearching = false;
      });
    }
  }

  String _getInitials(String name) {
    List<String> nameParts = name.split(" ");
    String initials = '';
    for (var part in nameParts) {
      if (part.isNotEmpty) {
        initials += part[0].toUpperCase();
      }
    }
    return initials.length > 2 ? initials.substring(0, 2) : initials;
  }

  void _showAddContactDialog() {
    final TextEditingController _contactNameController = TextEditingController();
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          title: const Text(
            "Add Contact",
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                "Enter the username of the contact you wish to add:",
                style: TextStyle(fontSize: 14, color: Colors.black54),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _contactNameController,
                decoration: InputDecoration(
                  hintText: "Contact username",
                  prefixIcon: const Icon(Icons.person),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(
                      color: AppColors.accent,
                      width: 2,
                    ),
                  ),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(context);
              },
              child: const Text("Cancel"),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              onPressed: () async {
                final contactName = _contactNameController.text.trim();
                final currentUser = ref.read(currentUserProvider)!;
                final contactsState = ref.read(
                  contactsProvider(currentUser.userId),
                );
                // Use the contacts notifier to add a new contact.
                final contactsNotifier = ref.read(
                  contactsProvider(currentUser.userId).notifier,
                );

                if (contactName.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Please enter a username")),
                  );
                  return;
                } else if (contactName == currentUser.username) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("You cannot add yourself")),
                  );
                  return;
                } else if (contactsState.contacts.any((contact) => contact.username == contactName)) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Contact already exists")),
                  );
                  return;
                }
                Navigator.pop(context); // Dismiss the dialog

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
    final currentUser = ref.watch(currentUserProvider);
    // Listen for changes in the contacts provider and update the orchestrator.
    ref.listen<ContactsState>(contactsProvider(currentUser!.userId), (previous, next) {
      // If an error occurs, show it as a SnackBar at the bottom.
      if (next.errorMessage != null && next.errorMessage!.isNotEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: Colors.red,
            content: Text(next.errorMessage!),
            duration: const Duration(seconds: 3),
          ),
        );
      }
      print("Contacts updated: ${next.contacts.length}");
      callOrchestrator.updateContacts(next.contacts);
    });

    // Watch the contacts provider for updates.
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
                      setState(() {
                        _searchQuery = query;
                      });
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
              // IconButton(
              //   icon: const Icon(Icons.history),
              //   onPressed: () {
              //     Navigator.push(
              //       context,
              //       MaterialPageRoute(
              //         builder: (context) => CallHistoryPage(
              //           service: callHistoryService,
              //           userId: currentUser.userId,
              //         ),
              //       ),
              //     );
              //   },
              // ),
              PopupMenuButton<String>(
                onSelected: (value) {
                  if (value == 'settings') {
                    // Navigate to settings page if needed.
                  }
                },
                itemBuilder: (context) => [
                  const PopupMenuItem<String>(
                    value: 'settings',
                    child: Text('Settings'),
                  ),
                  const PopupMenuItem<String>(
                    value: 'preferences',
                    child: Text('Preferences'),
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
                          style: const TextStyle(
                            color: AppColors.background,
                            fontSize: 20,
                          ),
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
                                (!contact.name.toLowerCase().contains(_searchQuery.toLowerCase()) ||
                                    !contact.username.toLowerCase().contains(_searchQuery.toLowerCase()))) {
                              return Container(); // Skip contacts that don't match search.
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
                                      style: const TextStyle(
                                        color: AppColors.textSecondary,
                                        fontSize: 12,
                                      )),
                                ],
                              ),
                              subtitle: const Text('Status: Online'),
                              trailing: IconButton(
                                icon: const Icon(Icons.video_call),
                                onPressed: () {
                                  callOrchestrator.callUser(contact);
                                },
                              ),
                            );
                          },
                        ),
                        // bottom right FAB (add contact)
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

                        // bottom left FAB (call history)
                        Positioned(
                          bottom: 24,
                          left: 24,
                          child: FloatingActionButton(
                            backgroundColor: AppColors.accent,
                            foregroundColor: AppColors.background,
                            onPressed: () {
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
          // floatingActionButton: FloatingActionButton(
          //   backgroundColor: AppColors.accent,
          //   foregroundColor: AppColors.background,
          //   onPressed: _showAddContactDialog,
          //   tooltip: 'Add Contact',
          //   child: const Icon(Icons.add),
          // ),
        ),
      ),
    );
  }
}
