import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../models/chat_models.dart';
import '../../providers/auth_provider.dart';
import 'widgets/message_bubble.dart';

class DmScreen extends ConsumerStatefulWidget {
  final DmConversation conversation;

  const DmScreen({super.key, required this.conversation});

  @override
  ConsumerState<DmScreen> createState() => _DmScreenState();
}

class _DmScreenState extends ConsumerState<DmScreen> {
  final _msgCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final _api = ApiClient();

  List<ChatMessage> _messages = [];
  bool _isLoading = true;
  bool _uploading = false;
  bool _sending = false;
  bool _hasMore = true;
  bool _loadingMore = false;

  @override
  void initState() {
    super.initState();
    _loadMessages();
    _scrollCtrl.addListener(_onScroll);
  }

  @override
  void dispose() {
    _msgCtrl.dispose();
    _scrollCtrl.dispose();
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
          '${AppConstants.dmMessagesUrl(widget.conversation.id)}?limit=50');
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
          '${AppConstants.dmMessagesUrl(widget.conversation.id)}?limit=50&before=$oldest');
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

  Future<void> _sendMessage() async {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty || _sending) return;
    _msgCtrl.clear();
    setState(() => _sending = true);
    try {
      final r = await _api.post(
        AppConstants.sendDmUrl(widget.conversation.id),
        {'content': text},
      );
      if (r.statusCode == 201) {
        final msg = ChatMessage.fromJson(jsonDecode(r.body));
        setState(() => _messages.add(msg));
        _scrollToBottom();
      }
    } catch (_) {}
    setState(() => _sending = false);
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
      final r = await _api.uploadFile(
        AppConstants.dmUploadUrl(widget.conversation.id),
        File(picked.path!),
        'file',
      );
      if (r.statusCode == 201) {
        final data = jsonDecode(r.body);
        final msg = ChatMessage.fromJson(data['message']);
        setState(() => _messages.add(msg));
        _scrollToBottom();
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
    final other = widget.conversation.otherUser;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
        title: Row(
          children: [
            CircleAvatar(
              radius: 18,
              backgroundImage: other.profilePicture != null
                  ? NetworkImage(other.profilePicture!)
                  : null,
              backgroundColor: AppColors.primary.withOpacity(0.15),
              child: other.profilePicture == null
                  ? Text(other.initial,
                      style: const TextStyle(
                          color: AppColors.primary, fontWeight: FontWeight.bold))
                  : null,
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(other.displayName,
                    style: const TextStyle(
                        fontWeight: FontWeight.w700, fontSize: 16)),
                Text('@${other.username}',
                    style: theme.textTheme.bodySmall),
              ],
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          if (_loadingMore) const LinearProgressIndicator(minHeight: 2),

          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            CircleAvatar(
                              radius: 40,
                              backgroundImage: other.profilePicture != null
                                  ? NetworkImage(other.profilePicture!)
                                  : null,
                              backgroundColor:
                                  AppColors.primary.withOpacity(0.15),
                              child: other.profilePicture == null
                                  ? Text(other.initial,
                                      style: const TextStyle(
                                          color: AppColors.primary,
                                          fontSize: 28,
                                          fontWeight: FontWeight.bold))
                                  : null,
                            ),
                            const SizedBox(height: 12),
                            Text(other.displayName,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700, fontSize: 18)),
                            const SizedBox(height: 4),
                            Text('Start a conversation with ${other.displayName}',
                                style: theme.textTheme.bodyMedium),
                          ],
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollCtrl,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
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

          _DmInputBar(
            controller: _msgCtrl,
            uploading: _uploading,
            sending: _sending,
            onSend: _sendMessage,
            onAttach: _pickAndUploadFile,
          ),
        ],
      ),
    );
  }
}

class _DmInputBar extends StatelessWidget {
  final TextEditingController controller;
  final bool uploading;
  final bool sending;
  final VoidCallback onSend;
  final VoidCallback onAttach;

  const _DmInputBar({
    required this.controller,
    required this.uploading,
    required this.sending,
    required this.onSend,
    required this.onAttach,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 12),
      decoration: BoxDecoration(
        color: theme.cardTheme.color ?? theme.colorScheme.surface,
        border: Border(
            top: BorderSide(
                color: theme.colorScheme.outline.withOpacity(0.3))),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            (uploading || sending)
                ? const Padding(
                    padding: EdgeInsets.all(8),
                    child: SizedBox(
                      width: 20,
                      height: 20,
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
                onSubmitted: (_) => onSend(),
                decoration: InputDecoration(
                  hintText: 'Message...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  filled: true,
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 8),
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
