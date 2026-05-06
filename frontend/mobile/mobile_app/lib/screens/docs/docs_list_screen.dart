import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../models/document.dart';
import '../../providers/workspace_provider.dart';
import 'document_detail_screen.dart';
import 'document_editor_screen.dart';

class DocsListScreen extends ConsumerStatefulWidget {
  const DocsListScreen({super.key});

  @override
  ConsumerState<DocsListScreen> createState() => _DocsListScreenState();
}

class _DocsListScreenState extends ConsumerState<DocsListScreen> {
  final _api = ApiClient();
  List<Document> _docs = [];
  bool _isLoading = false;
  String _query = '';
  // Track which workspace we last loaded so we don't reload unnecessarily.
  String? _lastLoadedWorkspaceId;

  @override
  void initState() {
    super.initState();
    // Trigger initial load after the first frame so `ref` is ready.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final workspaceId = ref.read(workspaceProvider).currentWorkspaceId;
      if (workspaceId != null) {
        _loadDocs();
      }
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
  }

  Future<void> _loadDocs() async {
    final workspaceId = ref.read(workspaceProvider).currentWorkspaceId;
    if (workspaceId == null) {
      if (mounted) setState(() => _isLoading = false);
      return;
    }
    if (mounted) setState(() => _isLoading = true);
    try {
      final response = await _api.get(AppConstants.workspaceDocumentsUrl(workspaceId));
      if (response.statusCode == 200) {
        final list = (jsonDecode(response.body) as List)
            .map((d) => Document.fromJson(d))
            .toList();
        if (mounted) {
          setState(() {
            _docs = list;
            _isLoading = false;
            _lastLoadedWorkspaceId = workspaceId;
          });
        }
      } else {
        if (mounted) setState(() => _isLoading = false);
      }
    } catch (_) {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  bool _isCreating = false;

  Future<void> _createDocument() async {
    if (_isCreating) return; // prevent double-tap duplicates
    final workspaceId = ref.read(workspaceProvider).currentWorkspaceId;
    if (workspaceId == null) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No workspace selected. Please select a workspace first.')),
        );
      }
      return;
    }
    try {
      setState(() => _isCreating = true);
      final response = await _api.post(
        AppConstants.documentsUrl,
        {'workspace_id': workspaceId, 'title': 'Untitled Document'},
      );
      if (response.statusCode == 201) {
        final data = jsonDecode(response.body);
        final documentId = data['document_id']?.toString();
        
        if (documentId == null || documentId.isEmpty) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Invalid response from server. Missing document ID.')),
            );
          }
          return;
        }
        
        final doc = Document(
          id: documentId,
          title: 'Untitled Document',
          workspaceId: workspaceId,
        );
        if (mounted) {
          // Reload docs AFTER returning from the editor, not before.
          await Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => DocumentEditorScreen(document: doc)),
          );
          // Refresh the list when the user comes back from the editor.
          if (mounted) _loadDocs();
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to create document. Server returned status ${response.statusCode}')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to create document: ${e.toString()}')),
        );
      }
    } finally {
      if (mounted) setState(() => _isCreating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // ref.listen fires on every build when the workspace ID changes.
    // This is the correct Riverpod pattern for triggering side-effects
    // (like loading data) in response to provider state changes.
    ref.listen<WorkspaceState>(workspaceProvider, (previous, next) {
      final newId = next.currentWorkspaceId;
      if (newId != null && newId != _lastLoadedWorkspaceId) {
        _loadDocs();
      }
    });

    final filtered = _docs
        .where((d) => d.title.toLowerCase().contains(_query.toLowerCase()))
        .toList();

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: const Text('Documents', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          IconButton(
            icon: _isCreating
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.add),
            onPressed: _isCreating ? null : _createDocument,
            tooltip: 'New document',
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              onChanged: (v) => setState(() => _query = v),
              decoration: const InputDecoration(
                hintText: 'Search documents...',
                prefixIcon: Icon(Icons.search),
              ),
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : RefreshIndicator(
                    onRefresh: _loadDocs,
                    child: _docs.isEmpty
                        // ── No documents exist at all ──────────────────────
                        ? LayoutBuilder(
                            builder: (context, constraints) => SingleChildScrollView(
                              physics: const AlwaysScrollableScrollPhysics(),
                              child: SizedBox(
                                height: constraints.maxHeight,
                                child: Center(
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(Icons.description_outlined,
                                          size: 64,
                                          color: theme.colorScheme.onSurface
                                              .withOpacity(0.3)),
                                      const SizedBox(height: 16),
                                      const Text('No documents yet'),
                                      const SizedBox(height: 12),
                                      ElevatedButton.icon(
                                        onPressed:
                                            _isCreating ? null : _createDocument,
                                        icon: _isCreating
                                            ? const SizedBox(
                                                width: 16,
                                                height: 16,
                                                child: CircularProgressIndicator(
                                                    strokeWidth: 2),
                                              )
                                            : const Icon(Icons.add),
                                        label: const Text('New Document'),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          )
                        : filtered.isEmpty
                            // ── Docs exist but search has no matches ───────
                            ? LayoutBuilder(
                                builder: (context, constraints) =>
                                    SingleChildScrollView(
                                  physics: const AlwaysScrollableScrollPhysics(),
                                  child: SizedBox(
                                    height: constraints.maxHeight,
                                    child: Center(
                                      child: Column(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Icon(Icons.search_off,
                                              size: 48,
                                              color: theme.colorScheme.onSurface
                                                  .withOpacity(0.3)),
                                          const SizedBox(height: 12),
                                          Text(
                                            'No results for "$_query"',
                                            style: theme.textTheme.bodyMedium,
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              )
                            // ── Normal list ────────────────────────────────
                            : ListView.builder(
                                physics: const AlwaysScrollableScrollPhysics(),
                                padding: const EdgeInsets.all(16),
                                itemCount: filtered.length,
                                itemBuilder: (context, i) => _DocCard(
                                  doc: filtered[i],
                                  onChanged: _loadDocs,
                                ),
                              ),
                  ),
          ),
        ],
      ),
    );
  }
}

class _DocCard extends StatelessWidget {
  final Document doc;
  final VoidCallback? onChanged;

  const _DocCard({required this.doc, this.onChanged});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        leading: Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: AppColors.primary.withOpacity(0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(Icons.description, color: AppColors.primary),
        ),
        title: Text(
          doc.title,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: doc.lastEditedBy != null
            ? Text(
                'Edited by ${doc.lastEditedBy}',
                style: theme.textTheme.bodySmall,
              )
            : null,
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (doc.collaboratorAvatars.isNotEmpty)
              SizedBox(
                width: 60,
                child: Stack(
                  children: doc.collaboratorAvatars
                      .take(3)
                      .toList()
                      .asMap()
                      .entries
                      .map((e) => Positioned(
                            left: e.key * 16.0,
                            child: CircleAvatar(
                              radius: 12,
                              backgroundImage: NetworkImage(e.value),
                            ),
                          ))
                      .toList(),
                ),
              ),
            IconButton(
              icon: const Icon(Icons.info_outline, size: 20),
              tooltip: 'Details',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => DocumentDetailScreen(
                    document: doc,
                    onChanged: onChanged,
                  ),
                ),
              ),
            ),
          ],
        ),
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => DocumentEditorScreen(document: doc)),
        ),
      ),
    );
  }
}
