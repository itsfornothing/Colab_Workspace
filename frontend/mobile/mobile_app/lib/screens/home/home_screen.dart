import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../core/theme.dart';
import '../../models/chat_models.dart';
import '../../models/workspace.dart';
import '../../providers/auth_provider.dart';
import '../../providers/notification_provider.dart';
import '../../providers/workspace_provider.dart';
import '../chat/messaging_screen.dart';
import '../notifications/notifications_panel.dart';
import '../workspace/workspace_screen.dart';

/// Converts a workspace [Channel] to a [ChatChannel] for use with [MessagingScreen].
ChatChannel channelFromWorkspaceChannel(Channel ch) => ChatChannel(
      id: ch.id,
      name: ch.name,
      description: '',
      isPrivate: ch.isPrivate,
      memberCount: ch.onlineCount,
      isJoined: true,
    );

class HomeScreen extends ConsumerStatefulWidget {
  final void Function(int) onSwitchTab;

  const HomeScreen({super.key, required this.onSwitchTab});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(workspaceProvider.notifier).loadWorkspaces();
    });
  }

  String _greeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final workspace = ref.watch(workspaceProvider);
    final notifState = ref.watch(notificationProvider);
    final theme = Theme.of(context);
    final firstName = auth.user?.fullName.split(' ').first ?? 'there';

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.workspaces_outlined),
          onPressed: () => _showWorkspaceSwitcher(context),
          tooltip: 'Switch workspace',
        ),
        title: GestureDetector(
          onTap: () => _openWorkspaceSettings(context),
          child: Text(
            workspace.currentWorkspace?.name ?? 'Collab',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => _openWorkspaceSettings(context),
            tooltip: 'Workspace settings',
          ),
          Stack(
            children: [
              IconButton(
                icon: const Icon(Icons.notifications_outlined),
                onPressed: () => _showNotifications(context),
              ),
              if (notifState.unreadCount > 0)
                Positioned(
                  right: 8,
                  top: 8,
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      color: AppColors.danger,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(workspaceProvider.notifier).loadWorkspaces(),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Greeting
              Text(
                '${_greeting()}, $firstName',
                style: theme.textTheme.displayLarge,
              ),
              const SizedBox(height: 4),
              Text(
                DateFormat('EEEE, MMMM d').format(DateTime.now()),
                style: theme.textTheme.bodyLarge,
              ),

              const SizedBox(height: 24),

              // Workspace cards
              if (workspace.workspaces.isNotEmpty) ...[
                Text('Workspaces', style: theme.textTheme.displayMedium),
                const SizedBox(height: 12),
                SizedBox(
                  height: 100,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: workspace.workspaces.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 12),
                    itemBuilder: (context, i) {
                      final ws = workspace.workspaces[i];
                      final isActive = ws.id == workspace.currentWorkspaceId;
                      return GestureDetector(
                        onTap: () => ref
                            .read(workspaceProvider.notifier)
                            .switchWorkspace(ws.id),
                        child: Container(
                          width: 140,
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: isActive
                                ? AppColors.primary
                                : theme.cardTheme.color,
                            borderRadius: BorderRadius.circular(16),
                            border: isActive
                                ? null
                                : Border.all(color: theme.colorScheme.outline),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                ws.name,
                                style: TextStyle(
                                  fontWeight: FontWeight.w600,
                                  color: isActive ? Colors.white : null,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                              Text(
                                '${ws.memberCount} members',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: isActive
                                      ? Colors.white70
                                      : theme.colorScheme.onSurface.withOpacity(0.5),
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 24),
              ],

              // Quick Actions
              Text('Quick Actions', style: theme.textTheme.displayMedium),
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 2.5,
                children: [
                  _QuickAction(
                    icon: Icons.add_circle_outline,
                    label: 'New Document',
                    onTap: () => widget.onSwitchTab(3),
                  ),
                  _QuickAction(
                    icon: Icons.chat_bubble_outline,
                    label: 'Start Chat',
                    onTap: () => widget.onSwitchTab(1),
                  ),
                  _QuickAction(
                    icon: Icons.video_call_outlined,
                    label: 'Start Call',
                    onTap: () => widget.onSwitchTab(2),
                  ),
                  _QuickAction(
                    icon: Icons.person_add_outlined,
                    label: 'Invite People',
                    onTap: () => showModalBottomSheet(
                      context: context,
                      shape: const RoundedRectangleBorder(
                        borderRadius:
                            BorderRadius.vertical(top: Radius.circular(20)),
                      ),
                      builder: (_) => _InviteSheet(
                        workspaceId: workspace.currentWorkspaceId,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 24),

              // Recent channels
              if (workspace.channels.isNotEmpty) ...[
                Text('Recent Channels', style: theme.textTheme.displayMedium),
                const SizedBox(height: 12),
                ...workspace.channels.take(5).map((ch) => ListTile(
                      contentPadding: EdgeInsets.zero,
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => MessagingScreen(
                            channel: channelFromWorkspaceChannel(ch),
                          ),
                        ),
                      ),
                      leading: Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: AppColors.primary.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Center(
                          child: Text(
                            '#',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: AppColors.primary,
                            ),
                          ),
                        ),
                      ),
                      title: Text(ch.name),
                      subtitle: ch.lastMessage != null
                          ? Text(
                              ch.lastMessage!,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            )
                          : null,
                      trailing: ch.unreadCount > 0
                          ? Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppColors.primary,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                '${ch.unreadCount}',
                                style: const TextStyle(
                                    color: Colors.white, fontSize: 12),
                              ),
                            )
                          : null,
                    )),
              ],
            ],
          ),
        ),
      ),
    );
  }

  void _showWorkspaceSwitcher(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => const _WorkspaceSwitcherSheet(),
    );
  }

  void _showNotifications(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => const NotificationsPanel(),
    );
  }

  void _openWorkspaceSettings(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const WorkspaceScreen()),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _QuickAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: theme.cardTheme.color,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: theme.colorScheme.outline),
        ),
        child: Row(
          children: [
            Icon(icon, color: AppColors.primary, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkspaceSwitcherSheet extends ConsumerWidget {
  const _WorkspaceSwitcherSheet();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final workspace = ref.watch(workspaceProvider);
    return DraggableScrollableSheet(
      initialChildSize: 0.5,
      minChildSize: 0.3,
      maxChildSize: 0.85,
      expand: false,
      builder: (context, scrollCtrl) => Padding(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Drag handle
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.outline,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const Text(
              'Switch Workspace',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: ListView(
                controller: scrollCtrl,
                children: [
                  ...workspace.workspaces.map((ws) => ListTile(
                        leading: CircleAvatar(
                          backgroundColor: AppColors.primary.withOpacity(0.1),
                          child: Text(
                            ws.name.isNotEmpty ? ws.name[0].toUpperCase() : 'W',
                            style: const TextStyle(color: AppColors.primary),
                          ),
                        ),
                        title: Text(ws.name),
                        subtitle: Text('${ws.memberCount} members'),
                        trailing: ws.id == workspace.currentWorkspaceId
                            ? const Icon(Icons.check, color: AppColors.primary)
                            : null,
                        onTap: () {
                          ref.read(workspaceProvider.notifier).switchWorkspace(ws.id);
                          Navigator.pop(context);
                        },
                      )),
                  const Divider(),
                  ListTile(
                    leading: const Icon(Icons.add_circle_outline, color: AppColors.primary),
                    title: const Text('Create New Workspace',
                        style: TextStyle(color: AppColors.primary)),
                    onTap: () async {
                      // Close the sheet first, then push CreateWorkspaceScreen
                      // on the root navigator so it sits above the home screen.
                      // CreateWorkspaceScreen already calls loadWorkspaces() before
                      // popping with true, so the provider is updated when we return.
                      // We call loadWorkspaces() here as well to guarantee a refresh
                      // even if the screen pops without going through _create().
                      final notifier = ref.read(workspaceProvider.notifier);
                      final rootNav = Navigator.of(context, rootNavigator: true);
                      // Pop the sheet synchronously.
                      rootNav.pop();
                      // Now push the creation screen on the root navigator.
                      final created = await rootNav.push<bool>(
                        MaterialPageRoute(builder: (_) => const CreateWorkspaceScreen()),
                      );
                      if (created == true) {
                        // CreateWorkspaceScreen already called loadWorkspaces(),
                        // but call again to ensure HomeScreen rebuilds with fresh data.
                        await notifier.loadWorkspaces();
                      }
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Invite Sheet
// ─────────────────────────────────────────────

class _InviteSheet extends StatelessWidget {
  final String? workspaceId;

  const _InviteSheet({this.workspaceId});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Invite People',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              const Icon(Icons.link, color: AppColors.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  workspaceId != null
                      ? 'Share an invite link for workspace $workspaceId'
                      : 'Select a workspace first to invite people.',
                  style: const TextStyle(fontSize: 14),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ),
        ],
      ),
    );
  }
}
