import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../models/workspace.dart';
import '../../providers/workspace_provider.dart';

class WorkspaceScreen extends ConsumerStatefulWidget {
  const WorkspaceScreen({super.key});

  @override
  ConsumerState<WorkspaceScreen> createState() => _WorkspaceScreenState();
}

class _WorkspaceScreenState extends ConsumerState<WorkspaceScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  final _api = ApiClient();

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final workspace = ref.watch(workspaceProvider);
    final theme = Theme.of(context);
    final ws = workspace.currentWorkspace;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: Text(ws?.name ?? 'Workspace',
            style: const TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_add_outlined),
            onPressed: () => _showInviteSheet(context),
            tooltip: 'Invite people',
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () {},
          ),
        ],
        bottom: TabBar(
          controller: _tabCtrl,
          tabs: const [
            Tab(text: 'Members'),
            Tab(text: 'Invite'),
            Tab(text: 'Settings'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabCtrl,
        children: [
          _MembersTab(workspaceId: ws?.id ?? ''),
          _InviteTab(workspaceId: ws?.id ?? ''),
          _SettingsTab(workspace: ws),
        ],
      ),
    );
  }

  void _showInviteSheet(BuildContext context) {
    final ws = ref.read(workspaceProvider).currentWorkspace;
    if (ws == null) return;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _InviteSheet(workspaceId: ws.id),
    );
  }
}

// ─────────────────────────────────────────────
// Members Tab
// ─────────────────────────────────────────────

class _MembersTab extends StatefulWidget {
  final String workspaceId;
  const _MembersTab({required this.workspaceId});

  @override
  State<_MembersTab> createState() => _MembersTabState();
}

class _MembersTabState extends State<_MembersTab> {
  final _api = ApiClient();
  List<WorkspaceMember> _members = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (widget.workspaceId.isEmpty) {
      setState(() => _loading = false);
      return;
    }
    try {
      final r = await _api.get(AppConstants.workspaceMembersUrl(widget.workspaceId));
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List)
            .map((m) => WorkspaceMember.fromJson(m))
            .toList();
        setState(() => _members = list);
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_members.isEmpty) {
      return const Center(child: Text('No members found'));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _members.length,
      itemBuilder: (_, i) {
        final m = _members[i];
        return ListTile(
          leading: CircleAvatar(
            backgroundImage: m.avatarUrl != null ? NetworkImage(m.avatarUrl!) : null,
            backgroundColor: AppColors.primary.withOpacity(0.15),
            child: m.avatarUrl == null
                ? Text(m.fullName.isNotEmpty ? m.fullName[0].toUpperCase() : '?',
                    style: const TextStyle(color: AppColors.primary))
                : null,
          ),
          title: Text(m.fullName, style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text(m.email),
          trailing: Chip(
            label: Text(m.role, style: const TextStyle(fontSize: 12)),
            padding: EdgeInsets.zero,
          ),
        );
      },
    );
  }
}

// ─────────────────────────────────────────────
// Invite Tab
// ─────────────────────────────────────────────

class _InviteTab extends StatefulWidget {
  final String workspaceId;
  const _InviteTab({required this.workspaceId});

  @override
  State<_InviteTab> createState() => _InviteTabState();
}

class _InviteTabState extends State<_InviteTab> {
  final _emailCtrl = TextEditingController();
  final _api = ApiClient();
  String _role = 'member';
  bool _loading = false;
  String? _message;
  String? _inviteLink;

  @override
  void dispose() {
    _emailCtrl.dispose();
    super.dispose();
  }

  Future<void> _sendInvite() async {
    final email = _emailCtrl.text.trim();
    if (email.isEmpty) return;
    setState(() { _loading = true; _message = null; });
    try {
      final r = await _api.post(AppConstants.inviteUserUrl, {
        'email': email,
        'role': _role,
        'workspace_id': widget.workspaceId,
      });
      if (r.statusCode == 201) {
        setState(() => _message = 'Invitation sent to $email');
        _emailCtrl.clear();
      } else {
        final err = jsonDecode(r.body);
        setState(() => _message = err['detail'] ?? 'Failed to send invitation.');
      }
    } catch (_) {
      setState(() => _message = 'Connection error.');
    }
    setState(() => _loading = false);
  }

  Future<void> _generateLink() async {
    setState(() => _loading = true);
    try {
      final r = await _api.post(
        AppConstants.workspaceInviteLinkUrl(widget.workspaceId),
        {'role': _role, 'expires_in_hours': 72},
      );
      if (r.statusCode == 201) {
        final data = jsonDecode(r.body);
        setState(() => _inviteLink = 'collab://join/${data['token']}');
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Invite by Email',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          TextField(
            controller: _emailCtrl,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(
              labelText: 'Email address',
              prefixIcon: Icon(Icons.email_outlined),
            ),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: _role,
            decoration: const InputDecoration(labelText: 'Role'),
            items: const [
              DropdownMenuItem(value: 'member', child: Text('Member')),
              DropdownMenuItem(value: 'admin', child: Text('Admin')),
              DropdownMenuItem(value: 'guest', child: Text('Guest')),
            ],
            onChanged: (v) => setState(() => _role = v ?? 'member'),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _loading ? null : _sendInvite,
              child: _loading
                  ? const SizedBox(width: 20, height: 20,
                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : const Text('Send Invitation'),
            ),
          ),
          if (_message != null) ...[
            const SizedBox(height: 8),
            Text(_message!, style: const TextStyle(color: AppColors.primary)),
          ],
          const SizedBox(height: 32),
          const Divider(),
          const SizedBox(height: 16),
          const Text('Invite Link',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text('Generate a shareable link that anyone can use to join.'),
          const SizedBox(height: 12),
          if (_inviteLink != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.05),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.primary.withOpacity(0.3)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(_inviteLink!,
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
                  ),
                  IconButton(
                    icon: const Icon(Icons.copy, size: 18),
                    onPressed: () {},
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
          ],
          OutlinedButton.icon(
            onPressed: _loading ? null : _generateLink,
            icon: const Icon(Icons.link),
            label: const Text('Generate Invite Link'),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Settings Tab
// ─────────────────────────────────────────────

class _SettingsTab extends ConsumerStatefulWidget {
  final Workspace? workspace;
  const _SettingsTab({this.workspace});

  @override
  ConsumerState<_SettingsTab> createState() => _SettingsTabState();
}

class _SettingsTabState extends ConsumerState<_SettingsTab> {
  final _api = ApiClient();
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _showEditDialog() async {
    final ws = widget.workspace;
    if (ws == null) return;

    // Pre-fill with current values
    _nameCtrl.text = ws.name;
    _descCtrl.text = ws.description ?? '';

    String? error;
    bool saving = false;

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Edit Workspace'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'Workspace name'),
                autofocus: true,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _descCtrl,
                decoration: const InputDecoration(labelText: 'Description'),
                maxLines: 3,
              ),
              if (error != null) ...[
                const SizedBox(height: 8),
                Text(error!, style: const TextStyle(color: AppColors.danger, fontSize: 13)),
              ],
            ],
          ),
          actions: [
            TextButton(
              onPressed: saving ? null : () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: saving
                  ? null
                  : () async {
                      final name = _nameCtrl.text.trim();
                      if (name.isEmpty) {
                        setDialogState(() => error = 'Name cannot be empty.');
                        return;
                      }
                      setDialogState(() { saving = true; error = null; });
                      try {
                        final r = await _api.patch(
                          AppConstants.workspaceUrl(ws.id),
                          {'name': name, 'description': _descCtrl.text.trim()},
                        );
                        if (r.statusCode == 200) {
                          await ref.read(workspaceProvider.notifier).loadWorkspaces();
                          if (ctx.mounted) Navigator.pop(ctx);
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Workspace updated.')),
                            );
                          }
                        } else {
                          final body = jsonDecode(r.body);
                          setDialogState(() {
                            error = body['detail'] ?? 'Failed to update.';
                            saving = false;
                          });
                        }
                      } catch (_) {
                        setDialogState(() {
                          error = 'Connection error.';
                          saving = false;
                        });
                      }
                    },
              child: saving
                  ? const SizedBox(
                      width: 18, height: 18,
                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmLeave() async {
    final ws = widget.workspace;
    if (ws == null) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Leave Workspace'),
        content: Text('Are you sure you want to leave "${ws.name}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Leave', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final r = await _api.post(AppConstants.leaveWorkspaceUrl(ws.id), {});
      if (r.statusCode == 200 || r.statusCode == 204) {
        await ref.read(workspaceProvider.notifier).loadWorkspaces();
        if (mounted) Navigator.of(context).pop();
      } else {
        final body = jsonDecode(r.body);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(body['detail'] ?? 'Failed to leave workspace.')),
          );
        }
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Connection error.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final ws = widget.workspace;
    if (ws == null) return const Center(child: Text('No workspace selected'));
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: CircleAvatar(
            radius: 28,
            backgroundColor: AppColors.primary.withOpacity(0.15),
            child: Text(
              ws.name.isNotEmpty ? ws.name[0].toUpperCase() : 'W',
              style: const TextStyle(
                  color: AppColors.primary, fontSize: 24, fontWeight: FontWeight.bold),
            ),
          ),
          title: Text(ws.name,
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18)),
          subtitle: Text('${ws.memberCount} members'),
        ),
        const SizedBox(height: 24),
        const Divider(),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.edit_outlined),
          title: const Text('Edit Workspace'),
          trailing: const Icon(Icons.chevron_right),
          onTap: _showEditDialog,
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.notifications_outlined),
          title: const Text('Notification Settings'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {},
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.exit_to_app, color: AppColors.danger),
          title: const Text('Leave Workspace',
              style: TextStyle(color: AppColors.danger)),
          onTap: _confirmLeave,
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────
// Invite Sheet (quick invite from home)
// ─────────────────────────────────────────────

class _InviteSheet extends StatefulWidget {
  final String workspaceId;
  const _InviteSheet({required this.workspaceId});

  @override
  State<_InviteSheet> createState() => _InviteSheetState();
}

class _InviteSheetState extends State<_InviteSheet> {
  final _ctrl = TextEditingController();
  final _api = ApiClient();
  bool _loading = false;
  String? _msg;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _invite() async {
    final email = _ctrl.text.trim();
    if (email.isEmpty) return;
    setState(() { _loading = true; _msg = null; });
    try {
      final r = await _api.post(AppConstants.inviteUserUrl, {
        'email': email,
        'workspace_id': widget.workspaceId,
        'role': 'member',
      });
      if (r.statusCode == 201) {
        setState(() => _msg = 'Invitation sent!');
        _ctrl.clear();
      } else {
        setState(() => _msg = 'Failed to send invitation.');
      }
    } catch (_) {
      setState(() => _msg = 'Connection error.');
    }
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Invite People',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 16),
            TextField(
              controller: _ctrl,
              autofocus: true,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(
                labelText: 'Email address',
                prefixIcon: Icon(Icons.email_outlined),
              ),
            ),
            if (_msg != null) ...[
              const SizedBox(height: 8),
              Text(_msg!, style: const TextStyle(color: AppColors.primary)),
            ],
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _loading ? null : _invite,
                child: _loading
                    ? const SizedBox(width: 20, height: 20,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Text('Send Invitation'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Create Workspace Screen
// ─────────────────────────────────────────────

class CreateWorkspaceScreen extends ConsumerStatefulWidget {
  const CreateWorkspaceScreen({super.key});

  @override
  ConsumerState<CreateWorkspaceScreen> createState() => _CreateWorkspaceScreenState();
}

class _CreateWorkspaceScreenState extends ConsumerState<CreateWorkspaceScreen> {
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  final _api = ApiClient();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Workspace name is required.');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final r = await _api.post(AppConstants.workspacesUrl, {
        'name': name,
        'description': _descCtrl.text.trim(),
      });
      if (r.statusCode == 201 && mounted) {
        await ref.read(workspaceProvider.notifier).loadWorkspaces();
        Navigator.pop(context, true);
      } else {
        final err = jsonDecode(r.body);
        setState(() => _error = err['detail'] ?? 'Failed to create workspace.');
      }
    } catch (_) {
      setState(() => _error = 'Connection error.');
    }
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Workspace'),
        backgroundColor: Theme.of(context).scaffoldBackgroundColor,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Create a new workspace for your team',
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 24),
            TextField(
              controller: _nameCtrl,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Workspace name',
                prefixIcon: Icon(Icons.workspaces_outlined),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _descCtrl,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Description (optional)',
                prefixIcon: Icon(Icons.info_outline),
                alignLabelWithHint: true,
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
            ],
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: _loading ? null : _create,
                child: _loading
                    ? const SizedBox(width: 20, height: 20,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Text('Create Workspace'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
