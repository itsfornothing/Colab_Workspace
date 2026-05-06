import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../providers/workspace_provider.dart';
import 'video_call_screen.dart';

class CallsScreen extends ConsumerStatefulWidget {
  /// Callback that switches the root [MainTabs] to the given tab index.
  final void Function(int) onSwitchTab;

  const CallsScreen({super.key, required this.onSwitchTab});

  @override
  ConsumerState<CallsScreen> createState() => _CallsScreenState();
}

class _CallsScreenState extends ConsumerState<CallsScreen> {
  final _api = ApiClient();
  List<Map<String, dynamic>> _rooms = [];
  bool _isLoading = true;
  String? _error;
  bool _isStartingCall = false;

  @override
  void initState() {
    super.initState();
    _loadRooms();
  }

  Future<void> _loadRooms() async {
    // workspaceId is read here only for the initial load; the build method
    // watches the provider reactively and shows the guard when it is null.
    final workspaceId = ref.read(workspaceProvider).currentWorkspaceId;
    if (workspaceId == null) {
      setState(() {
        _isLoading = false;
        _error = null;
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _api.get(
        '${AppConstants.roomsUrl}?workspace_id=$workspaceId',
      );
      if (response.statusCode == 200) {
        final list = List<Map<String, dynamic>>.from(jsonDecode(response.body));
        setState(() {
          _rooms = list;
          _isLoading = false;
        });
      } else {
        setState(() {
          _isLoading = false;
          _error = 'Failed to load rooms. Tap to retry.';
        });
      }
    } catch (_) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to load rooms. Tap to retry.';
      });
    }
  }

  Future<void> _startCall() async {
    final workspaceId = ref.read(workspaceProvider).currentWorkspaceId;
    if (workspaceId == null) return;

    setState(() => _isStartingCall = true);

    try {
      final response = await _api.post(
        AppConstants.roomsUrl,
        {'workspace_id': workspaceId},
      );
      if (response.statusCode == 201) {
        final room = jsonDecode(response.body);
        final roomId = room['id'];
        if (roomId == null) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Unexpected server response')),
            );
          }
          return;
        }
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => VideoCallScreen(roomId: roomId.toString()),
            ),
          );
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                'Failed to start call (${response.statusCode}). Please try again.',
              ),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to start call: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isStartingCall = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // Reactively watch the workspace provider so the guard updates automatically
    // when the user selects or deselects a workspace.
    final workspaceId = ref.watch(workspaceProvider).currentWorkspaceId;

    // ── Workspace guard ──────────────────────────────────────────────────────
    if (workspaceId == null) {
      return _NoWorkspaceView(onSwitchTab: widget.onSwitchTab);
    }

    // ── Loading state ────────────────────────────────────────────────────────
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(
          backgroundColor: theme.scaffoldBackgroundColor,
          elevation: 0,
          title: const Text('Calls', style: TextStyle(fontWeight: FontWeight.w700)),
        ),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    // ── Error state ──────────────────────────────────────────────────────────
    if (_error != null) {
      return Scaffold(
        appBar: AppBar(
          backgroundColor: theme.scaffoldBackgroundColor,
          elevation: 0,
          title: const Text('Calls', style: TextStyle(fontWeight: FontWeight.w700)),
        ),
        body: Center(
          child: Card(
            margin: const EdgeInsets.all(24),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.error_outline,
                      size: 48,
                      color: theme.colorScheme.error),
                  const SizedBox(height: 16),
                  Text(
                    _error!,
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: () {
                      setState(() => _error = null);
                      _loadRooms();
                    },
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    // ── Main content ─────────────────────────────────────────────────────────
    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Calls', style: TextStyle(fontWeight: FontWeight.w700)),
      ),
      body: Column(
        children: [
          // Start call button
          Padding(
            padding: const EdgeInsets.all(16),
            child: ElevatedButton.icon(
              onPressed: _isStartingCall ? null : _startCall,
              icon: _isStartingCall
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.video_call),
              label: Text(_isStartingCall ? 'Starting…' : 'Start a Call'),
            ),
          ),

          // Active rooms
          if (_rooms.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Active & Recent',
                  style: theme.textTheme.displayMedium,
                ),
              ),
            ),
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _rooms.length,
                itemBuilder: (context, i) {
                  final room = _rooms[i];
                  final isLive = room['is_active'] == true;
                  return Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    child: ListTile(
                      leading: Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: isLive
                              ? AppColors.danger.withOpacity(0.1)
                              : theme.colorScheme.outline.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          Icons.video_call,
                          color: isLive ? AppColors.danger : Colors.grey,
                        ),
                      ),
                      title: Text(room['name'] ?? 'Call Room'),
                      subtitle: Text(
                        isLive
                            ? '${room['participant_count'] ?? 0} participants'
                            : room['duration'] ?? 'Ended',
                      ),
                      trailing: isLive
                          ? Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: AppColors.danger,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Text(
                                'LIVE',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            )
                          : null,
                      onTap: isLive
                          ? () => Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => VideoCallScreen(
                                    roomId: room['id'].toString(),
                                  ),
                                ),
                              )
                          : null,
                    ),
                  );
                },
              ),
            ),
          ] else
            Expanded(
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.video_call_outlined,
                        size: 64,
                        color: theme.colorScheme.onSurface.withOpacity(0.3)),
                    const SizedBox(height: 16),
                    const Text('No recent calls'),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// ── _NoWorkspaceView ──────────────────────────────────────────────────────────

class _NoWorkspaceView extends StatelessWidget {
  final void Function(int) onSwitchTab;

  const _NoWorkspaceView({required this.onSwitchTab});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Calls', style: TextStyle(fontWeight: FontWeight.w700)),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.video_call_outlined,
                size: 72,
                color: theme.colorScheme.onSurface.withOpacity(0.3),
              ),
              const SizedBox(height: 24),
              Text(
                'Select a workspace to start or join calls',
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: () => onSwitchTab(0),
                icon: const Icon(Icons.home_outlined),
                label: const Text('Go to Home'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
