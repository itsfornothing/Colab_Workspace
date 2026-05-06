import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import 'dart:io';
import '../../core/api_client.dart';
import '../../core/cloudinary_service.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../models/user.dart';
import '../../providers/auth_provider.dart';
import '../../providers/theme_provider.dart';
import '../../providers/workspace_provider.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final _api = ApiClient();
  bool _isEditing = false;
  late TextEditingController _nameCtrl;
  late TextEditingController _titleCtrl;
  late TextEditingController _bioCtrl;
  String? _appVersion;
  bool _notifInApp = true;
  bool _notifEmail = false;

  @override
  void initState() {
    super.initState();
    final user = ref.read(authProvider).user;
    _nameCtrl = TextEditingController(text: user?.fullName ?? '');
    _titleCtrl = TextEditingController(text: user?.jobTitle ?? '');
    _bioCtrl = TextEditingController(text: user?.bio ?? '');
    PackageInfo.fromPlatform().then((info) {
      if (mounted) setState(() => _appVersion = info.version);
    });
    _loadNotifPrefs();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _titleCtrl.dispose();
    _bioCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadNotifPrefs() async {
    try {
      final r = await _api.get(AppConstants.notificationPrefsUrl);
      if (r.statusCode == 200 && mounted) {
        final data = jsonDecode(r.body);
        setState(() {
          _notifInApp = data['in_app'] ?? true;
          _notifEmail = data['email'] ?? false;
        });
      }
    } catch (_) {}
  }

  Future<void> _updateNotifPref({bool? inApp, bool? email}) async {
    final body = <String, dynamic>{};
    if (inApp != null) {
      setState(() => _notifInApp = inApp);
      body['in_app'] = inApp;
    }
    if (email != null) {
      setState(() => _notifEmail = email);
      body['email'] = email;
    }
    try {
      await _api.patch(AppConstants.notificationPrefsUrl, body);
    } catch (_) {}
  }

  void _showChangePasswordDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => const _ChangePasswordDialog(),
    );
  }

  Future<void> _openUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not open $url')),
      );
    }
  }

  Future<void> _confirmLeaveWorkspace(BuildContext context) async {
    final workspace = ref.read(workspaceProvider).currentWorkspace;
    if (workspace == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No workspace selected.')),
      );
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Leave Workspace'),
        content: Text('Leave "${workspace.name}"? You will lose access to all its content.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
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
      final r = await _api.post(AppConstants.leaveWorkspaceUrl(workspace.id), {});
      if ((r.statusCode == 200 || r.statusCode == 204) && mounted) {
        await ref.read(workspaceProvider.notifier).loadWorkspaces();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Left workspace.')),
        );
      } else if (mounted) {
        final body = jsonDecode(r.body);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(body['detail'] ?? 'Failed to leave workspace.')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Connection error.')),
        );
      }
    }
  }

  Future<void> _confirmDeleteWorkspace(BuildContext context) async {
    final workspace = ref.read(workspaceProvider).currentWorkspace;
    if (workspace == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No workspace selected.')),
      );
      return;
    }
    // Two-step confirmation for destructive action
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Workspace'),
        content: Text(
          'Permanently delete "${workspace.name}"?\n\nThis will delete all channels, documents, and messages. This cannot be undone.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete Forever', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      final r = await _api.delete(AppConstants.deleteWorkspaceUrl(workspace.id));
      if ((r.statusCode == 200 || r.statusCode == 204) && mounted) {
        await ref.read(workspaceProvider.notifier).loadWorkspaces();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Workspace deleted.')),
        );
      } else if (mounted) {
        final body = jsonDecode(r.body);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(body['detail'] ?? 'Failed to delete workspace.')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Connection error.')),
        );
      }
    }
  }

  Future<void> _saveProfile() async {
    if (_nameCtrl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Full name cannot be empty')),
      );
      return;
    }
    try {
      final r = await _api.patch(AppConstants.profileUpdateUrl, {
        'full_name': _nameCtrl.text.trim(),
        'job_title': _titleCtrl.text.trim(),
        'bio': _bioCtrl.text.trim(),
      });
      if (r.statusCode == 200) {
        // Update auth state immediately so the UI reflects the changes.
        final currentUser = ref.read(authProvider).user;
        if (currentUser != null) {
          ref.read(authProvider.notifier).updateUser(User(
            id: currentUser.id,
            email: currentUser.email,
            fullName: _nameCtrl.text.trim(),
            jobTitle: _titleCtrl.text.trim(),
            bio: _bioCtrl.text.trim(),
            avatarUrl: currentUser.avatarUrl,
          ));
        }
      }
      setState(() => _isEditing = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Profile updated'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e')),
        );
      }
    }
  }

  // ── Cloudinary avatar upload ─────────────────────────────────────────────

  Future<void> _pickAvatar() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 512,
      maxHeight: 512,
      imageQuality: 85,
    );
    if (picked == null) return;

    // Show uploading indicator
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Row(
            children: [
              SizedBox(
                width: 18, height: 18,
                child: CircularProgressIndicator(
                    color: Colors.white, strokeWidth: 2),
              ),
              SizedBox(width: 12),
              Text('Uploading avatar…'),
            ],
          ),
          duration: Duration(seconds: 10),
        ),
      );
    }

    final imageUrl = await CloudinaryService.upload(
      File(picked.path),
      resourceType: 'image',
    );

    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();

    if (imageUrl == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Upload failed. Try again.')),
      );
      return;
    }

    // Save the URL to the backend profile
    try {
      final r = await _api.patch(AppConstants.profileUpdateUrl, {'avatar_url': imageUrl});
      if (!mounted) return;

      if (r.statusCode == 200) {
        // Update auth state immediately with the new avatar URL — no round-trip needed.
        final currentUser = ref.read(authProvider).user;
        if (currentUser != null) {
          final updatedUser = User(
            id: currentUser.id,
            email: currentUser.email,
            fullName: currentUser.fullName,
            jobTitle: currentUser.jobTitle,
            bio: currentUser.bio,
            avatarUrl: imageUrl,
          );
          ref.read(authProvider.notifier).updateUser(updatedUser);
        }
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Avatar updated.'),
            backgroundColor: AppColors.success,
          ),
        );
      } else {
        // Show the actual server error to help diagnose
        String errMsg = 'Failed to save avatar (${r.statusCode}).';
        try {
          final body = jsonDecode(r.body);
          errMsg = body['error'] ?? body['detail'] ?? errMsg;
        } catch (_) {}
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(errMsg)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save avatar: $e')),
        );
      }
    }
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Sign out'),
        content: const Text('Are you sure you want to sign out?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Sign out', style: TextStyle(color: AppColors.danger)),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(authProvider.notifier).logout();
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final themeMode = ref.watch(themeProvider);
    final theme = Theme.of(context);
    final user = auth.user;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Profile', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          if (_isEditing)
            TextButton(
              onPressed: _saveProfile,
              child: const Text('Save', style: TextStyle(color: AppColors.primary)),
            )
          else
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () => setState(() => _isEditing = true),
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            // Avatar
            Center(
              child: Stack(
                children: [
                  CircleAvatar(
                    radius: 48,
                    backgroundImage: user?.avatarUrl != null
                        ? NetworkImage(user!.avatarUrl!)
                        : null,
                    backgroundColor: AppColors.primary.withOpacity(0.1),
                    child: user?.avatarUrl == null
                        ? Text(
                            () {
                              final src = (user?.fullName.isNotEmpty == true
                                      ? user!.fullName
                                      : null) ??
                                  user?.email ??
                                  'U';
                              return src.isNotEmpty ? src[0].toUpperCase() : 'U';
                            }(),
                            style: const TextStyle(
                              fontSize: 36,
                              color: AppColors.primary,
                              fontWeight: FontWeight.bold,
                            ),
                          )
                        : null,
                  ),
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: GestureDetector(
                      onTap: _pickAvatar,
                      child: Container(
                        padding: const EdgeInsets.all(6),
                        decoration: const BoxDecoration(
                          color: AppColors.primary,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.camera_alt, color: Colors.white, size: 16),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 8),
            Text(
              user?.email ?? '',
              style: theme.textTheme.bodySmall,
            ),

            const SizedBox(height: 24),

            // Editable fields
            if (_isEditing) ...[
              TextField(
                controller: _nameCtrl,
                decoration: const InputDecoration(
                  labelText: 'Full Name',
                  prefixIcon: Icon(Icons.person_outline),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _titleCtrl,
                decoration: const InputDecoration(
                  labelText: 'Job Title',
                  prefixIcon: Icon(Icons.work_outline),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _bioCtrl,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Bio',
                  prefixIcon: Icon(Icons.info_outline),
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 24),
            ] else ...[
              if (user?.fullName.isNotEmpty == true)
                _InfoRow(icon: Icons.person_outline, label: 'Name', value: user!.fullName),
              if (user?.jobTitle?.isNotEmpty == true)
                _InfoRow(icon: Icons.work_outline, label: 'Title', value: user!.jobTitle!),
              if (user?.bio?.isNotEmpty == true)
                _InfoRow(icon: Icons.info_outline, label: 'Bio', value: user!.bio!),
              const SizedBox(height: 16),
            ],

            // Settings sections
            _SectionHeader(title: 'Appearance'),
            _SettingsTile(
              icon: Icons.brightness_6_outlined,
              title: 'Theme',
              trailing: DropdownButton<ThemeMode>(
                value: themeMode,
                underline: const SizedBox(),
                items: const [
                  DropdownMenuItem(value: ThemeMode.system, child: Text('System')),
                  DropdownMenuItem(value: ThemeMode.light, child: Text('Light')),
                  DropdownMenuItem(value: ThemeMode.dark, child: Text('Dark')),
                ],
                onChanged: (mode) {
                  if (mode != null) ref.read(themeProvider.notifier).setTheme(mode);
                },
              ),
            ),

            const SizedBox(height: 8),
            _SectionHeader(title: 'Account'),
            _SettingsTile(
              icon: Icons.lock_outline,
              title: 'Change Password',
              onTap: () => _showChangePasswordDialog(context),
            ),
            _SettingsTile(
              icon: Icons.devices_outlined,
              title: 'Active Sessions',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ActiveSessionsScreen()),
              ),
            ),

            const SizedBox(height: 8),
            _SectionHeader(title: 'Notifications'),
            _SettingsTile(
              icon: Icons.notifications_outlined,
              title: 'In-app Notifications',
              trailing: Switch(
                value: _notifInApp,
                onChanged: (v) => _updateNotifPref(inApp: v),
                activeColor: AppColors.primary,
              ),
            ),
            _SettingsTile(
              icon: Icons.email_outlined,
              title: 'Email Alerts',
              trailing: Switch(
                value: _notifEmail,
                onChanged: (v) => _updateNotifPref(email: v),
                activeColor: AppColors.primary,
              ),
            ),

            const SizedBox(height: 8),
            _SectionHeader(title: 'Workspace'),
            _SettingsTile(
              icon: Icons.group_outlined,
              title: 'Team Members',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const TeamMembersScreen()),
              ),
            ),
            _SettingsTile(
              icon: Icons.exit_to_app,
              title: 'Leave Workspace',
              titleColor: AppColors.danger,
              onTap: () => _confirmLeaveWorkspace(context),
            ),
            _SettingsTile(
              icon: Icons.delete_forever_outlined,
              title: 'Delete Workspace',
              titleColor: AppColors.danger,
              onTap: () => _confirmDeleteWorkspace(context),
            ),

            const SizedBox(height: 8),
            _SectionHeader(title: 'Support'),
            _SettingsTile(
              icon: Icons.help_outline,
              title: 'Help Center',
              onTap: () => _openUrl('https://help.collabworkspace.app'),
            ),
            _SettingsTile(
              icon: Icons.privacy_tip_outlined,
              title: 'Privacy Policy',
              onTap: () => _openUrl('https://collabworkspace.app/privacy'),
            ),
            _SettingsTile(
              icon: Icons.info_outline,
              title: 'App Version',
              trailing: Text(_appVersion ?? '...'),
            ),

            const SizedBox(height: 24),

            // Sign out
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _logout,
                icon: const Icon(Icons.logout, color: AppColors.danger),
                label: const Text(
                  'Sign Out',
                  style: TextStyle(color: AppColors.danger),
                ),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: AppColors.danger),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _InfoRow({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppColors.primary),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.bodySmall),
              Text(value, style: const TextStyle(fontWeight: FontWeight.w500)),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;

  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(
          title.toUpperCase(),
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.2,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
      ),
    );
  }
}

class _SettingsTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final Color? titleColor;
  final Widget? trailing;
  final VoidCallback? onTap;

  const _SettingsTile({
    required this.icon,
    required this.title,
    this.titleColor,
    this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon, color: titleColor ?? Theme.of(context).colorScheme.onSurface),
      title: Text(
        title,
        style: TextStyle(color: titleColor),
      ),
      trailing: trailing ?? (onTap != null ? const Icon(Icons.chevron_right) : null),
      onTap: onTap,
    );
  }
}

// ─────────────────────────────────────────────
// Change Password Dialog
// ─────────────────────────────────────────────

class _ChangePasswordDialog extends StatefulWidget {
  const _ChangePasswordDialog();

  @override
  State<_ChangePasswordDialog> createState() => _ChangePasswordDialogState();
}

class _ChangePasswordDialogState extends State<_ChangePasswordDialog> {
  final _currentCtrl = TextEditingController();
  final _newCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  final _api = ApiClient();
  bool _loading = false;
  String? _error;
  bool _obscureCurrent = true;
  bool _obscureNew = true;
  bool _obscureConfirm = true;

  @override
  void dispose() {
    _currentCtrl.dispose();
    _newCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final current = _currentCtrl.text;
    final newPw = _newCtrl.text;
    final confirm = _confirmCtrl.text;

    if (current.isEmpty || newPw.isEmpty || confirm.isEmpty) {
      setState(() => _error = 'All fields are required.');
      return;
    }
    if (newPw.length < 8) {
      setState(() => _error = 'New password must be at least 8 characters.');
      return;
    }
    if (newPw != confirm) {
      setState(() => _error = 'New passwords do not match.');
      return;
    }

    setState(() { _loading = true; _error = null; });
    try {
      final r = await _api.post(AppConstants.passwordChangeUrl, {
        'current_password': current,
        'new_password': newPw,
      });
      if (r.statusCode == 200) {
        if (mounted) {
          Navigator.pop(context);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Password changed successfully.'),
              backgroundColor: AppColors.success,
            ),
          );
        }
      } else {
        final body = jsonDecode(r.body);
        setState(() => _error = body['error'] ?? body['detail'] ?? 'Failed to change password.');
      }
    } catch (_) {
      setState(() => _error = 'Connection error.');
    }
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Change Password'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _currentCtrl,
              obscureText: _obscureCurrent,
              decoration: InputDecoration(
                labelText: 'Current Password',
                prefixIcon: const Icon(Icons.lock_outline),
                suffixIcon: IconButton(
                  icon: Icon(_obscureCurrent ? Icons.visibility_off : Icons.visibility),
                  onPressed: () => setState(() => _obscureCurrent = !_obscureCurrent),
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _newCtrl,
              obscureText: _obscureNew,
              decoration: InputDecoration(
                labelText: 'New Password',
                prefixIcon: const Icon(Icons.lock_outline),
                suffixIcon: IconButton(
                  icon: Icon(_obscureNew ? Icons.visibility_off : Icons.visibility),
                  onPressed: () => setState(() => _obscureNew = !_obscureNew),
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _confirmCtrl,
              obscureText: _obscureConfirm,
              decoration: InputDecoration(
                labelText: 'Confirm New Password',
                prefixIcon: const Icon(Icons.lock_outline),
                suffixIcon: IconButton(
                  icon: Icon(_obscureConfirm ? Icons.visibility_off : Icons.visibility),
                  onPressed: () => setState(() => _obscureConfirm = !_obscureConfirm),
                ),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: const TextStyle(color: AppColors.danger, fontSize: 13)),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _loading ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _loading ? null : _submit,
          child: _loading
              ? const SizedBox(width: 18, height: 18,
                  child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
              : const Text('Change Password'),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────
// Active Sessions Screen
// ─────────────────────────────────────────────

class ActiveSessionsScreen extends StatefulWidget {
  const ActiveSessionsScreen({super.key});

  @override
  State<ActiveSessionsScreen> createState() => _ActiveSessionsScreenState();
}

class _ActiveSessionsScreenState extends State<ActiveSessionsScreen> {
  final _api = ApiClient();
  List<Map<String, dynamic>> _sessions = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final r = await _api.get(AppConstants.sessionsUrl);
      if (r.statusCode == 200 && mounted) {
        setState(() => _sessions = List<Map<String, dynamic>>.from(jsonDecode(r.body)));
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _revoke(String sessionId) async {
    try {
      final r = await _api.delete(AppConstants.sessionUrl(sessionId));
      if ((r.statusCode == 200 || r.statusCode == 204) && mounted) {
        setState(() => _sessions.removeWhere((s) => s['id'] == sessionId));
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Session revoked.')),
        );
      }
    } catch (_) {}
  }

  String _formatDate(String? iso) {
    if (iso == null) return 'Unknown';
    try {
      final dt = DateTime.parse(iso).toLocal();
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
          '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Active Sessions', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _sessions.isEmpty
              ? const Center(child: Text('No active sessions found.'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _sessions.length,
                  itemBuilder: (_, i) {
                    final s = _sessions[i];
                    final ua = s['user_agent'] ?? 'Unknown device';
                    final ip = s['ip_address'] ?? 'Unknown IP';
                    final lastUsed = _formatDate(s['last_used_at']);
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ListTile(
                        leading: const Icon(Icons.devices_outlined, color: AppColors.primary),
                        title: Text(
                          ua.length > 40 ? '${ua.substring(0, 40)}…' : ua,
                          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                        ),
                        subtitle: Text('IP: $ip\nLast used: $lastUsed',
                            style: const TextStyle(fontSize: 12)),
                        isThreeLine: true,
                        trailing: IconButton(
                          icon: const Icon(Icons.logout, color: AppColors.danger),
                          tooltip: 'Revoke session',
                          onPressed: () => _revoke(s['id']),
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}

// ─────────────────────────────────────────────
// Team Members Screen
// ─────────────────────────────────────────────

class TeamMembersScreen extends ConsumerStatefulWidget {
  const TeamMembersScreen({super.key});

  @override
  ConsumerState<TeamMembersScreen> createState() => _TeamMembersScreenState();
}

class _TeamMembersScreenState extends ConsumerState<TeamMembersScreen> {
  final _api = ApiClient();
  List<Map<String, dynamic>> _members = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final workspaceId = ref.read(workspaceProvider).currentWorkspaceId;
    if (workspaceId == null) {
      setState(() => _loading = false);
      return;
    }
    setState(() => _loading = true);
    try {
      final r = await _api.get(AppConstants.workspaceMembersUrl(workspaceId));
      if (r.statusCode == 200 && mounted) {
        setState(() => _members = List<Map<String, dynamic>>.from(jsonDecode(r.body)));
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Team Members', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _members.isEmpty
              ? const Center(child: Text('No members found.'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _members.length,
                  itemBuilder: (_, i) {
                    final m = _members[i];
                    final user = m['user'] as Map<String, dynamic>? ?? m;
                    final name = user['full_name'] ?? user['username'] ?? 'Unknown';
                    final email = user['email'] ?? '';
                    final role = m['role'] ?? 'member';
                    final initials = name.isNotEmpty ? name[0].toUpperCase() : '?';
                    return ListTile(
                      leading: CircleAvatar(
                        backgroundColor: AppColors.primary.withOpacity(0.15),
                        child: Text(initials,
                            style: const TextStyle(color: AppColors.primary)),
                      ),
                      title: Text(name,
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text(email),
                      trailing: Chip(
                        label: Text(role, style: const TextStyle(fontSize: 12)),
                        padding: EdgeInsets.zero,
                      ),
                    );
                  },
                ),
    );
  }
}
