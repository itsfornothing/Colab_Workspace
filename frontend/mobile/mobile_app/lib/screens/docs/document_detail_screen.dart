import 'dart:convert';
import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../models/document.dart';
import 'document_editor_screen.dart';

class DocumentDetailScreen extends StatefulWidget {
  final Document document;
  final VoidCallback? onChanged; // called after rename/delete so list refreshes

  const DocumentDetailScreen({
    super.key,
    required this.document,
    this.onChanged,
  });

  @override
  State<DocumentDetailScreen> createState() => _DocumentDetailScreenState();
}

class _DocumentDetailScreenState extends State<DocumentDetailScreen> {
  final _api = ApiClient();
  bool _loadingVersions = false;
  List _versions = [];

  @override
  void initState() {
    super.initState();
    _loadVersions();
  }

  Future<void> _loadVersions() async {
    setState(() => _loadingVersions = true);
    try {
      final r = await _api.get(AppConstants.documentVersionsUrl(widget.document.id));
      if (r.statusCode == 200 && mounted) {
        setState(() => _versions = jsonDecode(r.body) as List);
      }
    } catch (_) {}
    if (mounted) setState(() => _loadingVersions = false);
  }

  Future<void> _rename() async {
    final ctrl = TextEditingController(text: widget.document.title);
    final newTitle = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Rename Document'),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Title'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
            child: const Text('Rename'),
          ),
        ],
      ),
    );
    ctrl.dispose();
    if (newTitle == null || newTitle.isEmpty || newTitle == widget.document.title) return;

    try {
      final r = await _api.patch(
        AppConstants.documentUpdateUrl(widget.document.id),
        {'title': newTitle},
      );
      if (r.statusCode == 200 && mounted) {
        widget.onChanged?.call();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Document renamed.')),
        );
        Navigator.pop(context);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to rename.')),
        );
      }
    }
  }

  Future<void> _delete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Document'),
        content: Text('Delete "${widget.document.title}"? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      // Use archive endpoint (soft delete)
      final r = await _api.post(
        AppConstants.documentArchiveUrl(widget.document.id),
        {},
      );
      if (!mounted) return;
      if (r.statusCode == 200 || r.statusCode == 204) {
        widget.onChanged?.call();
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Document deleted.')),
        );
      } else if (r.statusCode == 403) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('You do not have permission to delete this document.'),
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete (${r.statusCode}).')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to delete.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final doc = widget.document;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Document Details',
            style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          PopupMenuButton<String>(
            onSelected: (v) {
              if (v == 'rename') _rename();
              if (v == 'delete') _delete();
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'rename', child: Text('Rename')),
              const PopupMenuItem(
                value: 'delete',
                child: Text('Delete', style: TextStyle(color: AppColors.danger)),
              ),
            ],
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // Doc icon + title
          Center(
            child: Column(
              children: [
                Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Icon(Icons.description,
                      color: AppColors.primary, size: 40),
                ),
                const SizedBox(height: 12),
                Text(
                  doc.title,
                  style: const TextStyle(
                      fontSize: 20, fontWeight: FontWeight.w700),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Open button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (_) => DocumentEditorScreen(document: doc)),
              ),
              icon: const Icon(Icons.edit_outlined),
              label: const Text('Open & Edit'),
            ),
          ),

          const SizedBox(height: 24),
          const Divider(),
          const SizedBox(height: 8),

          // Info section
          _InfoRow(
            icon: Icons.badge_outlined,
            label: 'Document ID',
            value: doc.id,
          ),
          if (doc.lastEditedBy != null)
            _InfoRow(
              icon: Icons.person_outline,
              label: 'Last edited by',
              value: doc.lastEditedBy!,
            ),
          if (doc.lastEditedAt != null)
            _InfoRow(
              icon: Icons.access_time,
              label: 'Last edited',
              value: _formatDate(doc.lastEditedAt!),
            ),

          const SizedBox(height: 16),
          const Divider(),
          const SizedBox(height: 8),

          // Actions
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.drive_file_rename_outline),
            title: const Text('Rename'),
            trailing: const Icon(Icons.chevron_right),
            onTap: _rename,
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.history),
            title: const Text('Version History'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _showVersionHistory(context),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.delete_outline, color: AppColors.danger),
            title: const Text('Delete Document',
                style: TextStyle(color: AppColors.danger)),
            onTap: _delete,
          ),

          // Version history preview
          if (_versions.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 8),
            Text('Recent Versions',
                style: theme.textTheme.titleSmall
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            ..._versions.take(5).map((v) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.history, size: 20),
                  title: Text('Version ${v['version_number'] ?? ''}'),
                  subtitle: Text(
                    v['created_at']?.toString().substring(0, 16) ?? '',
                    style: theme.textTheme.bodySmall,
                  ),
                )),
          ],
          if (_loadingVersions)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Center(child: CircularProgressIndicator()),
            ),
        ],
      ),
    );
  }

  void _showVersionHistory(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.5,
        builder: (_, ctrl) => Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Version History',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 16),
              if (_versions.isEmpty)
                const Text('No versions recorded yet.')
              else
                Expanded(
                  child: ListView.builder(
                    controller: ctrl,
                    itemCount: _versions.length,
                    itemBuilder: (_, i) {
                      final v = _versions[i];
                      return ListTile(
                        leading: CircleAvatar(
                          radius: 16,
                          backgroundColor: AppColors.primary.withOpacity(0.1),
                          child: Text(
                            '${v['version_number'] ?? i + 1}',
                            style: const TextStyle(
                                color: AppColors.primary, fontSize: 12),
                          ),
                        ),
                        title: Text('Version ${v['version_number'] ?? i + 1}'),
                        subtitle: Text(
                          v['created_at']?.toString().substring(0, 16) ?? '',
                        ),
                      );
                    },
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: Colors.grey),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: const TextStyle(fontSize: 12, color: Colors.grey)),
                const SizedBox(height: 2),
                Text(value,
                    style: const TextStyle(fontWeight: FontWeight.w500)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
