import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import '../../core/api_client.dart';
import '../../core/cloudinary_service.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../providers/workspace_provider.dart';

class WorkspaceFile {
  final String id;
  final String name;
  final String fileUrl;
  final int fileSize;
  final String mimeType;
  final DateTime createdAt;

  const WorkspaceFile({
    required this.id,
    required this.name,
    required this.fileUrl,
    required this.fileSize,
    required this.mimeType,
    required this.createdAt,
  });

  factory WorkspaceFile.fromJson(Map<String, dynamic> j) => WorkspaceFile(
        id: j['id']?.toString() ?? '',
        name: j['name'] ?? '',
        fileUrl: j['file_url'] ?? '',
        fileSize: j['file_size'] ?? 0,
        mimeType: j['mime_type'] ?? '',
        createdAt: DateTime.tryParse(j['created_at'] ?? '') ?? DateTime.now(),
      );

  bool get isImage {
    final lower = name.toLowerCase();
    return lower.endsWith('.jpg') || lower.endsWith('.jpeg') ||
        lower.endsWith('.png') || lower.endsWith('.gif') || lower.endsWith('.webp');
  }

  IconData get icon {
    final lower = name.toLowerCase();
    if (lower.endsWith('.pdf')) return Icons.picture_as_pdf_outlined;
    if (lower.endsWith('.doc') || lower.endsWith('.docx')) return Icons.description_outlined;
    if (lower.endsWith('.xls') || lower.endsWith('.xlsx')) return Icons.table_chart_outlined;
    if (lower.endsWith('.zip') || lower.endsWith('.rar')) return Icons.folder_zip_outlined;
    if (isImage) return Icons.image_outlined;
    return Icons.insert_drive_file_outlined;
  }

  String get sizeLabel {
    if (fileSize < 1024) return '${fileSize}B';
    if (fileSize < 1024 * 1024) return '${(fileSize / 1024).toStringAsFixed(1)}KB';
    return '${(fileSize / (1024 * 1024)).toStringAsFixed(1)}MB';
  }
}

class FilesScreen extends ConsumerStatefulWidget {
  const FilesScreen({super.key});

  @override
  ConsumerState<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends ConsumerState<FilesScreen> {
  final _api = ApiClient();
  final _searchCtrl = TextEditingController();
  List<WorkspaceFile> _files = [];
  bool _loading = true;
  bool _uploading = false;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final wsId = ref.read(workspaceProvider).currentWorkspaceId;
    if (wsId == null) {
      setState(() => _loading = false);
      return;
    }
    setState(() => _loading = true);
    try {
      final url = _query.isEmpty
          ? '${AppConstants.filesUrl}?workspace_id=$wsId'
          : '${AppConstants.filesUrl}?workspace_id=$wsId&q=${Uri.encodeComponent(_query)}';
      final r = await _api.get(url);
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List)
            .map((j) => WorkspaceFile.fromJson(j))
            .toList();
        setState(() => _files = list);
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  Future<void> _upload() async {
    final wsId = ref.read(workspaceProvider).currentWorkspaceId;
    if (wsId == null) return;

    final result = await FilePicker.platform.pickFiles(
      allowMultiple: false,
      type: FileType.any,
    );
    if (result == null || result.files.isEmpty) return;
    final picked = result.files.first;
    if (picked.path == null) return;

    setState(() => _uploading = true);
    try {
      // Upload directly to Cloudinary; send the resulting URL to the backend.
      final fileUrl = await CloudinaryService.upload(File(picked.path!));
      if (fileUrl == null) {
        _showError('Upload failed.');
        setState(() => _uploading = false);
        return;
      }

      // Save the Cloudinary URL + metadata to the backend (no file re-upload).
      final r = await _api.post(AppConstants.fileUploadUrl, {
        'workspace_id': wsId,
        'file_url': fileUrl,
        'name': picked.name,
        'file_size': picked.size,
        'mime_type': picked.extension ?? 'application/octet-stream',
      });
      if (r.statusCode == 201) {
        _load();
      } else {
        _showError('Upload failed.');
      }
    } catch (_) {
      _showError('Upload failed. Check your connection.');
    }
    setState(() => _uploading = false);
  }

  Future<void> _delete(WorkspaceFile file) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete file'),
        content: Text('Delete "${file.name}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete', style: TextStyle(color: AppColors.danger)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _api.delete(AppConstants.fileDeleteUrl(file.id));
      _load();
    } catch (_) {}
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Files', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          _uploading
              ? const Padding(
                  padding: EdgeInsets.all(12),
                  child: SizedBox(
                    width: 20, height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                )
              : IconButton(
                  icon: const Icon(Icons.upload_file_outlined),
                  onPressed: _upload,
                  tooltip: 'Upload file',
                ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              controller: _searchCtrl,
              onChanged: (v) {
                setState(() => _query = v);
                _load();
              },
              decoration: InputDecoration(
                hintText: 'Search files...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _query.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchCtrl.clear();
                          setState(() => _query = '');
                          _load();
                        },
                      )
                    : null,
              ),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _load,
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _files.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.folder_open_outlined,
                                  size: 64, color: Colors.grey.shade400),
                              const SizedBox(height: 12),
                              Text(
                                _query.isNotEmpty ? 'No files found' : 'No files yet',
                                style: theme.textTheme.bodyLarge,
                              ),
                              const SizedBox(height: 12),
                              ElevatedButton.icon(
                                onPressed: _upload,
                                icon: const Icon(Icons.upload),
                                label: const Text('Upload File'),
                              ),
                            ],
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: _files.length,
                          itemBuilder: (_, i) => _FileTile(
                            file: _files[i],
                            onDelete: () => _delete(_files[i]),
                          ),
                        ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FileTile extends StatelessWidget {
  final WorkspaceFile file;
  final VoidCallback onDelete;

  const _FileTile({required this.file, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: AppColors.primary.withOpacity(0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: file.isImage
              ? ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: Image.network(
                    file.fileUrl,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) =>
                        Icon(file.icon, color: AppColors.primary),
                  ),
                )
              : Icon(file.icon, color: AppColors.primary),
        ),
        title: Text(
          file.name,
          style: const TextStyle(fontWeight: FontWeight.w500),
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          '${file.sizeLabel} • ${_formatDate(file.createdAt)}',
          style: theme.textTheme.bodySmall,
        ),
        trailing: PopupMenuButton<String>(
          onSelected: (v) {
            if (v == 'delete') onDelete();
          },
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'delete', child: Text('Delete')),
          ],
        ),
      ),
    );
  }

  String _formatDate(DateTime dt) {
    return '${dt.month}/${dt.day}/${dt.year}';
  }
}
