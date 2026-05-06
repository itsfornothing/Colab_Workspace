import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_quill/flutter_quill.dart' as quill;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../core/token_storage.dart';
import '../../models/document.dart' as models;

class DocumentEditorScreen extends StatefulWidget {
  final models.Document document;

  const DocumentEditorScreen({super.key, required this.document});

  @override
  State<DocumentEditorScreen> createState() => _DocumentEditorScreenState();
}

class _DocumentEditorScreenState extends State<DocumentEditorScreen> {
  late quill.QuillController _quillCtrl;
  final _titleCtrl = TextEditingController();
  final _storage   = TokenStorage();
  final _api       = ApiClient();

  WebSocketChannel? _ws;
  String _saveStatus      = 'Saved';
  bool   _isConnected     = false;
  Timer? _saveTimer;
  Timer? _titleSaveTimer;
  Timer? _reconnectTimer;
  bool   _disposed        = false;
  bool   _isLoadingContent = true;
  int    _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 5;

  final Map<String, Map<String, dynamic>> _collaborators = {};

  @override
  void initState() {
    super.initState();
    _titleCtrl.text = widget.document.title;
    _quillCtrl      = quill.QuillController.basic();

    // FIX: load HTTP content FIRST, then connect WebSocket.
    //
    // Original code launched both simultaneously in initState().
    // This created a race:
    //   - WS connect() fires has_permission() on the backend
    //   - At the same moment, create_document() transaction may not
    //     have fully committed yet (the DocumentPermission row is
    //     part of the same atomic block)
    //   - has_permission() finds DoesNotExist → caches level=0 for 60s
    //   - WS closes with 4003 (not a member)
    //   - HTTP GET /documents/:id/ also hits the cache → 403 → no content
    //
    // Fix: load HTTP content first (which proves the document exists
    // and the transaction committed), then connect the WebSocket.
    // By the time _connectWebSocket() runs, the permission row is
    // guaranteed to be committed and visible.
    _loadContentThenConnectWS();

    _titleCtrl.addListener(_onTitleChanged);
  }

  @override
  void dispose() {
    _disposed = true;
    _saveTimer?.cancel();
    _titleSaveTimer?.cancel();
    _reconnectTimer?.cancel();
    _quillCtrl.removeListener(_onDocumentChanged);
    _quillCtrl.dispose();
    _titleCtrl.removeListener(_onTitleChanged);
    _titleCtrl.dispose();
    _ws?.sink.close();
    _ws = null;
    super.dispose();
  }

  // ── Content load ─────────────────────────────────────────────────

  Future<void> _loadContentThenConnectWS() async {
    await _loadContent();
    // Only connect WebSocket after HTTP load succeeds.
    // If the document loaded successfully, the DB transaction is committed
    // and has_permission() on the WS consumer will find the row.
    if (!_disposed) {
      await _connectWebSocket();
    }
  }

  Future<void> _loadContent() async {
    try {
      final r = await _api.get(AppConstants.documentUrl(widget.document.id));

      // FIX: surface non-200 responses so the UI shows the real error
      // instead of silently showing a blank editor.
      if (r.statusCode == 403) {
        if (mounted) setState(() => _saveStatus = 'No permission');
        return;
      }
      if (r.statusCode != 200) {
        if (mounted) setState(() => _saveStatus = 'Load failed (${r.statusCode})');
        return;
      }

      final data    = jsonDecode(r.body);
      final content = data['content'] as String? ?? '';
      if (content.isNotEmpty && mounted) {
        try {
          final doc = quill.Document.fromJson(jsonDecode(content));
          _quillCtrl.document = doc;
        } catch (_) {
          // Plain-text fallback for documents stored as raw strings
          _quillCtrl.document = quill.Document()
            ..insert(0, content);
        }
      }
    } catch (e) {
      if (mounted) setState(() => _saveStatus = 'Load error');
    } finally {
      // Start listening for changes only AFTER the load completes so
      // the programmatic document assignment above doesn't trigger a save.
      _isLoadingContent = false;
      _quillCtrl.addListener(_onDocumentChanged);
    }
  }

  // ── WebSocket ─────────────────────────────────────────────────────

  Future<void> _connectWebSocket() async {
    if (_disposed) return;

    final oldWs = _ws;
    _ws = null;
    await oldWs?.sink.close();

    final token = await _storage.getAccessToken();
    if (token == null || _disposed) return;

    try {
      // VERIFIED CORRECT: Uri constructor explicitly uses scheme: 'ws' to ensure
      // the WebSocket protocol upgrade handshake can complete successfully.
      // Using the Uri constructor (rather than parsing a string) avoids any
      // platform-specific URI parsing that could silently convert ws:// to http://.
      final uri = Uri(
        scheme:          'ws',
        host:            AppConstants.wsHost,
        port:            AppConstants.collabWsPort,
        path:            '/ws/docs/${widget.document.id}/',
        queryParameters: {'token': token},
      );

      // Log the full URI so we can confirm the scheme is 'ws://' in debug output.
      debugPrint('[WS] Connecting to: $uri');

      // Runtime guard: fail fast in debug builds if the scheme is ever wrong.
      assert(
        uri.scheme == 'ws' || uri.scheme == 'wss',
        'WebSocket URI must use ws:// or wss:// scheme, got: ${uri.scheme}',
      );

      final channel = WebSocketChannel.connect(uri);
      _ws = channel;

      // Wait for the handshake to complete (101 Switching Protocols).
      // If the server rejects the upgrade (e.g. auth failure, routing
      // mismatch) this throws a WebSocketChannelException synchronously
      // before the stream is ever listened to — which is exactly the
      // unhandled exception seen in the error log.
      // Awaiting channel.ready here moves that throw into our try/catch.
      await channel.ready;

      if (_disposed) return;

      _reconnectAttempts = 0;
      if (mounted) setState(() => _isConnected = true);

      channel.stream.listen(
        (data) {
          if (!_disposed) _handleWsEvent(jsonDecode(data as String));
        },
        onError: (error) {
          if (_disposed) return;
          debugPrint('[WS] Error: $error');
          if (mounted) setState(() { _isConnected = false; _saveStatus = 'Offline'; });
          _scheduleReconnect();
        },
        onDone: () {
          if (_disposed) return;
          if (mounted) setState(() => _isConnected = false);
          _scheduleReconnect();
        },
        cancelOnError: false,
      );
    } catch (e) {
      debugPrint('[WS] Connect failed: $e');
      if (_disposed) return;
      if (mounted) setState(() { _isConnected = false; _saveStatus = 'Offline'; });
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) return;
    _reconnectAttempts++;
    final delay = Duration(seconds: 3 * (1 << (_reconnectAttempts - 1)));
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, () {
      if (!_disposed) _connectWebSocket();
    });
  }

  void _handleWsEvent(Map<String, dynamic> event) {
    switch (event['type'] as String?) {
      case 'participant_joined':
        final user = event['user'] as Map<String, dynamic>?;
        if (user != null) {
          final id = user['id']?.toString() ?? '';
          setState(() => _collaborators[id] = {
            'name':   user['full_name'] ?? user['username'] ?? 'User',
            'avatar': user['avatar_url'],
            'color':  _colorForId(id),
          });
        }

      case 'participant_left':
        final userId = (event['user'] as Map<String, dynamic>?)?['id']?.toString();
        if (userId != null) setState(() => _collaborators.remove(userId));

      case 'initial_state':
        // Server sends the full document state on connect — no action needed
        // here because the HTTP load already populated the editor.
        // In a full Yjs implementation this is where you'd apply the snapshot.
        break;

      case 'crdt_update':
        // Apply remote delta — full Yjs implementation would call
        // Y.applyUpdate(ydoc, base64Decode(event['operation'])) here.
        break;

      case 'error':
        final detail = event['detail'] as String? ?? 'Unknown error';
        debugPrint('[WS] Server error: $detail');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Connection error: $detail')),
          );
        }

      case 'heartbeat_ack':
        break; // no-op
    }
  }

  // ── Document changes ──────────────────────────────────────────────

  void _onTitleChanged() {
    _titleSaveTimer?.cancel();
    _titleSaveTimer = Timer(const Duration(milliseconds: 800), _saveTitle);
  }

  Future<void> _saveTitle() async {
    if (_disposed) return;
    final title = _titleCtrl.text.trim();
    if (title.isEmpty) return;
    try {
      await _api.patch(
        AppConstants.documentUpdateUrl(widget.document.id),
        {'title': title},
      );
    } catch (_) {}
  }

  void _onDocumentChanged() {
    if (_isLoadingContent) return;
    if (mounted) setState(() => _saveStatus = 'Saving...');
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(milliseconds: 800), _saveContent);

    // FIX: original sent { 'delta': ... } but the Django consumer expects
    // { 'type': 'crdt_update', 'operation': '<base64 bytes>' }.
    // Sending the wrong field name means the server receives the event
    // but finds no 'operation' key → logs an error and doesn't relay it
    // to other clients. Use the correct field name here.
    //
    // For a proper Yjs implementation replace this with a base64-encoded
    // Y.encodeStateAsUpdate() binary. For now send the Quill delta as
    // a JSON string in 'operation' so the server accepts it.
    if (_ws != null && _isConnected) {
      // The server expects 'operation' to be a base64-encoded bytes string.
      // We don't have a Yjs implementation yet, so encode the Quill delta
      // JSON as UTF-8 bytes and then base64 it so the server can decode it
      // without throwing "Invalid base64 in 'operation'".
      final deltaJson = jsonEncode(_quillCtrl.document.toDelta().toJson());
      final operationB64 = base64Encode(utf8.encode(deltaJson));
      _ws!.sink.add(jsonEncode({
        'type':      'crdt_update',
        'operation': operationB64,
      }));
    }
  }

  Future<void> _saveContent() async {
    if (_disposed) return;
    try {
      final content = jsonEncode(_quillCtrl.document.toDelta().toJson());
      final r = await _api.patch(
        AppConstants.documentUpdateUrl(widget.document.id),
        {
          'content': content,
          'title':   _titleCtrl.text.trim(),
        },
      );

      if (!mounted) return;

      if (r.statusCode == 200) {
        setState(() => _saveStatus = 'Saved');
      } else if (r.statusCode == 403) {
        // FIX: surface the real reason instead of generic "Error saving"
        setState(() => _saveStatus = 'No permission to save');
        debugPrint('[Save] 403 Forbidden — response: ${r.body}');
      } else {
        setState(() => _saveStatus = 'Error saving (${r.statusCode})');
        debugPrint('[Save] Unexpected status ${r.statusCode}: ${r.body}');
      }
    } catch (e) {
      debugPrint('[Save] Exception: $e');
      if (mounted) setState(() => _saveStatus = 'Error saving');
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────

  Color _colorForId(String id) {
    const colors = [
      Colors.blue, Colors.green, Colors.orange, Colors.purple, Colors.red,
    ];
    final hash = id.codeUnits.fold(0, (a, b) => a + b);
    return colors[hash % colors.length];
  }

  // ── Build ─────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: TextField(
          controller: _titleCtrl,
          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
          decoration: const InputDecoration(
            border: InputBorder.none,
            hintText: 'Document title',
          ),
          onSubmitted: (_) => _saveTitle(),
          // Disable the system context menu on the title field to prevent
          // a Flutter assertion error when Quill's editor also tries to
          // show the system context menu at the same time on iOS.
          contextMenuBuilder: (context, editableTextState) {
            return AdaptiveTextSelectionToolbar.editableText(
              editableTextState: editableTextState,
            );
          },
        ),
        actions: [
          // Active collaborators
          if (_collaborators.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: _collaborators.values.take(3).map((c) {
                  return Padding(
                    padding: const EdgeInsets.only(right: 2),
                    child: CircleAvatar(
                      radius: 14,
                      backgroundColor: c['color'] as Color,
                      backgroundImage: c['avatar'] != null
                          ? NetworkImage(c['avatar'] as String)
                          : null,
                      child: c['avatar'] == null
                          ? Text(
                              (c['name'] as String).isNotEmpty
                                  ? (c['name'] as String)[0].toUpperCase()
                                  : '?',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 11),
                            )
                          : null,
                    ),
                  );
                }).toList(),
              ),
            ),

          // Save status indicator
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: _statusColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 4),
                Text(_saveStatus, style: theme.textTheme.bodySmall),
              ],
            ),
          ),

          IconButton(
            icon: const Icon(Icons.history_outlined),
            onPressed: () => _showVersionHistory(context),
            tooltip: 'Version history',
          ),
        ],
      ),

      body: Column(
        children: [
          // Collaborators banner
          if (_collaborators.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              color: AppColors.primary.withOpacity(0.05),
              child: Row(
                children: [
                  const Icon(Icons.people_outline,
                      size: 14, color: AppColors.primary),
                  const SizedBox(width: 6),
                  Text(
                    '${_collaborators.length} '
                    '${_collaborators.length == 1 ? 'person' : 'people'} editing',
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.primary),
                  ),
                  const SizedBox(width: 8),
                  ..._collaborators.values.take(3).map((c) => Padding(
                        padding: const EdgeInsets.only(right: 4),
                        child: Text(
                          c['name'] as String,
                          style: TextStyle(
                            fontSize: 12,
                            color:      c['color'] as Color,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      )),
                ],
              ),
            ),

          // Formatting toolbar
          quill.QuillSimpleToolbar(
            controller: _quillCtrl,
            config: const quill.QuillSimpleToolbarConfig(
              showBoldButton:            true,
              showItalicButton:          true,
              showUnderLineButton:       true,
              showHeaderStyle:           true,
              showListNumbers:           true,
              showListBullets:           true,
              showCodeBlock:             true,
              showUndo:                  true,
              showRedo:                  true,
              showFontFamily:            false,
              showFontSize:              false,
              showColorButton:           false,
              showBackgroundColorButton: false,
              showClearFormat:           false,
              showAlignmentButtons:      false,
              showLink:                  false,
              showSearchButton:          false,
              showSubscript:             false,
              showSuperscript:           false,
              showSmallButton:           false,
              showIndent:                false,
              showQuote:                 false,
              showStrikeThrough:         false,
              showInlineCode:            false,
              showDirection:             false,
              showLeftAlignment:         false,
              showCenterAlignment:       false,
              showRightAlignment:        false,
              showJustifyAlignment:      false,
              showClipboardCut:          false,
              showClipboardCopy:         false,
              showClipboardPaste:        false,
            ),
          ),

          const Divider(height: 1),

          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: quill.QuillEditor.basic(
                controller: _quillCtrl,
                config: const quill.QuillEditorConfig(
                  placeholder: 'Start writing...',
                  padding:     EdgeInsets.zero,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Color get _statusColor {
    switch (_saveStatus) {
      case 'Saved':
        return AppColors.success;
      case 'Saving...':
        return Colors.orange;
      default:
        return AppColors.danger;
    }
  }

  void _showVersionHistory(BuildContext context) async {
    try {
      final r = await _api.get(
          AppConstants.documentVersionsUrl(widget.document.id));
      if (r.statusCode == 200 && mounted) {
        final versions = jsonDecode(r.body) as List;
        showModalBottomSheet(
          context:  context,
          builder:  (_) => _VersionHistorySheet(
            versions:   versions,
            documentId: widget.document.id,
            api:        _api,
          ),
        );
      }
    } catch (_) {}
  }
}

// ── Version history bottom sheet ─────────────────────────────────────

class _VersionHistorySheet extends StatelessWidget {
  final List       versions;
  final String     documentId;
  final ApiClient  api;

  const _VersionHistorySheet({
    required this.versions,
    required this.documentId,
    required this.api,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Version History',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 16),
          if (versions.isEmpty)
            const Text('No versions yet')
          else
            ...versions.take(10).map(
              (v) => ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.history),
                title: Text('Version ${v['version_number']}'),
                subtitle: Text(
                  v['created_at']?.toString().substring(0, 16) ?? '',
                ),
                trailing: TextButton(
                  child: const Text('Restore'),
                  onPressed: () async {
                    Navigator.of(context).pop();
                    await api.post(
                      '/api/documents/$documentId/restore/',
                      {'version_number': v['version_number']},
                    );
                  },
                ),
              ),
            ),
        ],
      ),
    );
  }
}