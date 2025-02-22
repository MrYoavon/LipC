import 'dart:async';

import 'package:flutter/material.dart';

import '../helpers/call_orchestrator.dart';
import '../helpers/server_helper.dart';

class ContactsPage extends StatefulWidget {
  final ServerHelper serverHelper;
  final String?
      profileImage; // Profile image path (can be null or empty if no image exists)
  final String username; // User's name to extract initials

  const ContactsPage(
      {super.key,
      required this.serverHelper,
      required this.profileImage,
      required this.username});

  @override
  _ContactsPageState createState() => _ContactsPageState();
}

class _ContactsPageState extends State<ContactsPage> {
  bool _isSearching = false;
  String _searchQuery = '';
  final FocusNode _searchFocusNode = FocusNode();

  late CallOrchestrator callOrchestrator;

  late Future<List<Map<String, dynamic>>> _contactsFuture;

  @override
  void initState() {
    super.initState();
    _contactsFuture = widget.serverHelper.fetchContacts();

    callOrchestrator = CallOrchestrator(
      serverHelper: widget.serverHelper,
      localUsername: widget.username,
      context: context,
    );
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

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _onTapOutside, // Detect taps outside the search field
      child: Scaffold(
        appBar: AppBar(
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
                  style: const TextStyle(color: Colors.black),
                  decoration: const InputDecoration(
                    hintText: 'Search contacts...',
                    hintStyle: TextStyle(color: Colors.black54),
                    border: InputBorder.none,
                  ),
                )
              : const Center(
                  child: Text('Lip-C', style: TextStyle(color: Colors.black)),
                ),
          actions: [
            PopupMenuButton<String>(
              onSelected: (value) {
                // Handle menu option
                if (value == 'settings') {
                  // Navigate to settings page
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
                backgroundImage: widget.profileImage != null &&
                        widget.profileImage!.isNotEmpty
                    ? AssetImage(widget.profileImage!) as ImageProvider
                    : null, // Use null if no image exists
                child: widget.profileImage == null ||
                        widget.profileImage!.isEmpty
                    ? Text(
                        _getInitials(widget.username),
                        style:
                            const TextStyle(color: Colors.white, fontSize: 20),
                      )
                    : null, // Display initials if no image is found
              ),
              padding: const EdgeInsets.only(right: 16),
            ),
          ],
        ),
        body: FutureBuilder<List<Map<String, dynamic>>>(
          future: _contactsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            } else if (snapshot.hasError) {
              return Center(child: Text("Error: ${snapshot.error}"));
            } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
              return const Center(child: Text("No contacts found."));
            } else {
              final contacts = snapshot.data!;
              return ListView.builder(
                itemCount: contacts.length,
                itemBuilder: (context, index) {
                  final contact = contacts[index];
                  if (_searchQuery.isNotEmpty &&
                      !contact['name']
                          .toLowerCase()
                          .contains(_searchQuery.toLowerCase())) {
                    return Container(); // Skip contacts that don't match the search query
                  }
                  return ListTile(
                    leading: CircleAvatar(
                      child: Text(
                          contact['name']![0]), // Use initials as a placeholder
                    ),
                    title: Text(contact['name']),
                    subtitle: const Text('Status: Online'),
                    trailing: IconButton(
                      icon: const Icon(Icons.video_call),
                      onPressed: () {
                        callOrchestrator.callUser(contact['name']);
                      },
                    ),
                  );
                },
              );
            }
          },
        ),
        floatingActionButton: FloatingActionButton(
          onPressed: () {
            // Add new contact
          },
          tooltip: 'Add Contact',
          child: const Icon(Icons.add),
        ),
      ),
    );
  }
}
