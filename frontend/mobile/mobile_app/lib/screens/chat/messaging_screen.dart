import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/api_client.dart';
import '../../core/cloudinary_service.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../core/token_storage.dart';
import '../../models/chat_models.dart';
import '../../providers/auth_provider.dart';
import 'widgets/message_bubble.dart';

class MessagingScreen extends ConsumerStatefulWidget {
  final ChatChannel channel;

  const MessagingScreen({super.key, required this.channel});

  @override
  ConsumerState<MessagingScreen> createState() => _MessagingScreenState();
}

class _MessagingScreenState extends ConsumerState<MessagingScreen> {
  final _msgCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final _api = ApiClient();
  final _storage = TokenStorage();

  WebSocketChannel? _ws;
  List<ChatMessage> _messages = [];
  Set<String> _typingUsers = {};
  bool _isLoading = true;
  bool _uploading = false;
  bool _hasMore = true;
  bool _loadingMore = false;
  bool _disposed = false;
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 5;

  @override
  void initState() {
    super.initState();
    _loadMessages();
    _connectWebSocket();
    _scrollCtrl.addListener(_onScroll);
  }

  @override
  void dispose() {
    _disposed = true;
    _msgCtrl.dispose();
    _scrollCtrl.dispose();
    _ws?.sink.close();
    _ws = null;
    super.dispose();
  }

  void _onScroll() {
    if (_scrollCtrl.position.pixels <= 100 && _hasMore && !_loadingMore) {
      _loadMoreMessages();
    }
  }

  Future<void> _loadMessages() async {
    try {
      final r = await _api.get(
          '${AppConstants.channelMessagesUrl(widget.channel.id)}?limit=50');
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List)
            .map((m) => ChatMessage.fromJson(m))
            .toList();
        setState(() {
          _messages = list;
          _isLoading = false;
          _hasMore = list.length >= 50;
        });
        _scrollToBottom();
      } else {
        setState(() => _isLoading = false);
      }
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _loadMoreMessages() async {
    if (_messages.isEmpty) return;
    setState(() => _loadingMore = true);
    try {
      final oldest = _messages.first.id;
      final r = await _api.get(
          '${AppConstants.channelMessagesUrl(widget.channel.id)}?limit=50&before=$oldest');
      if (r.statusCode == 200) {
        final list = (jsonDecode(r.body) as List)
            .map((m) => ChatMessage.fromJson(m))
            .toList();
        setState(() {
          _messages.insertAll(0, list);
          _hasMore = list.length >= 50;
        });
      }
    } catch (_) {}
    setState(() => _loadingMore = false);
  }

  Future<void> _connectWebSocket() async {
    if (_disposed) return;
    final token = await _storage.getAccessToken();
    if (token == null || _disposed) return;
    try {
      final oldWs = _ws;
      _ws = null;
      await oldWs?.sink.close();

      _ws = WebSocketChannel.connect(
        Uri.parse(AppConstants.chatWs(widget.channel.id, token)),
      );
      _reconnectAttempts = 0;

      _ws!.stream.listen(
        (data) {
          if (!_disposed) _handleWsEvent(jsonDecode(data));
        },
        onError: (_) {
          if (_disposed) return;
          _scheduleReconnect();
        },
        onDone: () {
          if (_disposed) return;
          // Reload messages in case we missed any while disconnected.
          if (mounted) _loadMessages();
          _scheduleReconnect();
        },
        cancelOnError: false,
      );
    } catch (_) {
      if (_disposed) return;
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_disposed || _reconnectAttempts >= _maxReconnectAttempts) return;
    _reconnectAttempts++;
    final delay = Duration(seconds: 3 * (1 << (_reconnectAttempts - 1)));
    Future.delayed(delay, () {
      if (!_disposed && mounted) _connectWebSocket();
    });
  }

  void _handleWsEvent(Map<String, dynamic> event) {
    final type = event['type'];
    if (type == 'message' || type == 'chat_message') {
      // WS sends minimal data; reload last message from REST for full sender info
      _loadMessages();
    } else if (type == 'typing') {
      final user = event['user']?.toString() ?? '';
      if (user.isNotEmpty) {
        setState(() => _typingUsers.add(user));
        Future.delayed(const Duration(seconds: 3), () {
          if (mounted) setState(() => _typingUsers.remove(user));
        });
      }
    } else if (type == 'edit') {
      final msgId = event['message_id']?.toString();
      final content = event['content']?.toString() ?? '';
      if (msgId != null) {
        setState(() {
          final idx = _messages.indexWhere((m) => m.id == msgId);
          if (idx != -1) {
            final old = _messages[idx];
            _messages[idx] = ChatMessage(
              id: old.id,
              channelId: old.channelId,
              sender: old.sender,
              content: content,
              messageType: old.messageType,
              fileUrl: old.fileUrl,
              fileName: old.fileName,
              isEdited: true,
              isDeleted: old.isDeleted,
              createdAt: old.createdAt,
            );
          }
        });
      }
    } else if (type == 'delete') {
      final msgId = event['message_id']?.toString();
      if (msgId != null) {
        setState(() {
          final idx = _messages.indexWhere((m) => m.id == msgId);
          if (idx != -1) {
            final old = _messages[idx];
            _messages[idx] = ChatMessage(
              id: old.id,
              channelId: old.channelId,
              sender: old.sender,
              content: old.content,
              messageType: old.messageType,
              fileUrl: old.fileUrl,
              fileName: old.fileName,
              isEdited: old.isEdited,
              isDeleted: true,
              createdAt: old.createdAt,
            );
          }
        });
      }
    }
  }

  void _sendMessage() {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty) return;
    _msgCtrl.clear();

    if (_ws != null) {
      _ws!.sink.add(jsonEncode({'type': 'message', 'message': text}));
      // Reload after a short delay to pick up the saved message.
      Future.delayed(const Duration(milliseconds: 500), () {
        if (mounted) _loadMessages();
      });
    } else {
      // WebSocket not connected — send via REST to ensure message is persisted.
      _sendMessageViaRest(text);
    }
  }

  Future<void> _sendMessageViaRest(String text) async {
    try {
      final r = await _api.post(
        AppConstants.channelMessagesUrl(widget.channel.id),
        {'content': text, 'message_type': 'text'},
      );
      if (r.statusCode == 201 && mounted) {
        _loadMessages();
      }
    } catch (_) {
      // Silently ignore — WS reconnect will sync state on recovery.
    }
  }

  void _sendTyping() {
    _ws?.sink.add(jsonEncode({'type': 'typing'}));
  }

  Future<void> _pickAndUploadFile() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: false,
      type: FileType.any,
    );
    if (result == null || result.files.isEmpty) return;
    final picked = result.files.first;
    if (picked.path == null) return;

    setState(() => _uploading = true);
    try {
      // Upload directly to Cloudinary; backend only stores the URL.
      final fileUrl = await CloudinaryService.upload(File(picked.path!));
      if (fileUrl == null) {
        _showError('Upload failed.');
        setState(() => _uploading = false);
        return;
      }

      // Notify the backend with the Cloudinary URL (no file re-upload).
      final r = await _api.post(
        AppConstants.channelUploadUrl(widget.channel.id),
        {
          'cloudinary_url': fileUrl,
          'file_name': picked.name,
          'file_size': picked.size,
        },
      );
      if (r.statusCode == 201) {
        final data = jsonDecode(r.body);
        _ws?.sink.add(jsonEncode({
          'type': 'file',
          'file_url': data['file_url'] ?? fileUrl,
          'file_name': data['file_name'] ?? picked.name,
        }));
        Future.delayed(const Duration(milliseconds: 500), _loadMessages);
      } else {
        _showError('Upload failed.');
      }
    } catch (_) {
      _showError('Upload failed. Check your connection.');
    }
    setState(() => _uploading = false);
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final theme = Theme.of(context);
    final myId = auth.user?.id ?? '';

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  widget.channel.isPrivate ? Icons.lock_outline : Icons.tag,
                  size: 16,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 4),
                Text(widget.channel.name,
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 17)),
              ],
            ),
            Text('${widget.channel.memberCount} members',
                style: theme.textTheme.bodySmall),
          ],
        ),
      ),
      body: Column(
        children: [
          if (_loadingMore)
            const LinearProgressIndicator(minHeight: 2),

          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.chat_bubble_outline,
                                size: 64, color: Colors.grey.shade400),
                            const SizedBox(height: 12),
                            Text('No messages yet. Say hello!',
                                style: theme.textTheme.bodyLarge),
                          ],
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollCtrl,
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        itemCount: _messages.length,
                        itemBuilder: (_, i) {
                          final msg = _messages[i];
                          final isOwn = msg.sender.id == myId;
                          final showHeader = i == 0 ||
                              _messages[i - 1].sender.id != msg.sender.id;
                          return MessageBubble(
                            message: msg,
                            isOwn: isOwn,
                            showHeader: showHeader,
                          );
                        },
                      ),
          ),

          if (_typingUsers.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  '${_typingUsers.first} is typing...',
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontStyle: FontStyle.italic,
                    color: AppColors.primary,
                  ),
                ),
              ),
            ),

          _InputBar(
            controller: _msgCtrl,
            uploading: _uploading,
            onSend: _sendMessage,
            onTyping: _sendTyping,
            onAttach: _pickAndUploadFile,
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Input Bar
// ─────────────────────────────────────────────

class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final bool uploading;
  final VoidCallback onSend;
  final VoidCallback onTyping;
  final VoidCallback onAttach;

  const _InputBar({
    required this.controller,
    required this.uploading,
    required this.onSend,
    required this.onTyping,
    required this.onAttach,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 12),
      decoration: BoxDecoration(
        color: theme.cardTheme.color ?? theme.colorScheme.surface,
        border: Border(top: BorderSide(color: theme.colorScheme.outline.withOpacity(0.3))),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            uploading
                ? const Padding(
                    padding: EdgeInsets.all(8),
                    child: SizedBox(
                      width: 20, height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : IconButton(
                    icon: const Icon(Icons.attach_file),
                    onPressed: onAttach,
                    tooltip: 'Attach file',
                  ),
            Expanded(
              child: TextField(
                controller: controller,
                maxLines: null,
                textInputAction: TextInputAction.send,
                onChanged: (_) => onTyping(),
                onSubmitted: (_) => onSend(),
                decoration: InputDecoration(
                  hintText: 'Message...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  filled: true,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                ),
              ),
            ),
            const SizedBox(width: 4),
            IconButton(
              icon: const Icon(Icons.send, color: AppColors.primary),
              onPressed: onSend,
            ),
          ],
        ),
      ),
    );
  }
}
