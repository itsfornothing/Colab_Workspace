import 'package:flutter/material.dart';
import '../../../core/theme.dart';
import '../../../models/chat_models.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final bool isOwn;
  final bool showHeader;

  const MessageBubble({
    super.key,
    required this.message,
    required this.isOwn,
    required this.showHeader,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment:
            isOwn ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isOwn) ...[
            if (showHeader)
              CircleAvatar(
                radius: 16,
                backgroundImage: message.sender.profilePicture != null
                    ? NetworkImage(message.sender.profilePicture!)
                    : null,
                backgroundColor: AppColors.primary.withOpacity(0.15),
                child: message.sender.profilePicture == null
                    ? Text(message.sender.initial,
                        style: const TextStyle(
                            color: AppColors.primary, fontSize: 12))
                    : null,
              )
            else
              const SizedBox(width: 32),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Column(
              crossAxisAlignment: isOwn
                  ? CrossAxisAlignment.end
                  : CrossAxisAlignment.start,
              children: [
                if (showHeader && !isOwn)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 2, left: 4),
                    child: Text(
                      message.sender.displayName,
                      style: const TextStyle(
                          fontWeight: FontWeight.w600, fontSize: 12),
                    ),
                  ),
                Container(
                  constraints: BoxConstraints(
                    maxWidth: MediaQuery.of(context).size.width * 0.72,
                  ),
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: isOwn
                        ? AppColors.primary
                        : (theme.cardTheme.color ??
                            theme.colorScheme.surfaceContainerHighest),
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(18),
                      topRight: const Radius.circular(18),
                      bottomLeft: Radius.circular(isOwn ? 18 : 4),
                      bottomRight: Radius.circular(isOwn ? 4 : 18),
                    ),
                  ),
                  child: message.isDeleted
                      ? Text(
                          'Message deleted',
                          style: TextStyle(
                            fontStyle: FontStyle.italic,
                            color: isOwn
                                ? Colors.white60
                                : theme.colorScheme.onSurface.withOpacity(0.4),
                          ),
                        )
                      : message.isFile
                          ? _FileAttachment(
                              fileUrl: message.fileUrl ?? '',
                              fileName: message.fileName ?? 'File',
                              isOwn: isOwn,
                            )
                          : Text(
                              message.content,
                              style: TextStyle(
                                color: isOwn
                                    ? Colors.white
                                    : theme.colorScheme.onSurface,
                              ),
                            ),
                ),
                Padding(
                  padding: const EdgeInsets.only(top: 2, left: 4, right: 4),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        _formatTime(message.createdAt),
                        style: theme.textTheme.bodySmall
                            ?.copyWith(fontSize: 10),
                      ),
                      if (message.isEdited) ...[
                        const SizedBox(width: 4),
                        Text(
                          '(edited)',
                          style: theme.textTheme.bodySmall
                              ?.copyWith(fontSize: 10),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(DateTime dt) {
    final now = DateTime.now();
    if (dt.day == now.day && dt.month == now.month && dt.year == now.year) {
      return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    }
    return '${dt.month}/${dt.day} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}

class _FileAttachment extends StatelessWidget {
  final String fileUrl;
  final String fileName;
  final bool isOwn;

  const _FileAttachment({
    required this.fileUrl,
    required this.fileName,
    required this.isOwn,
  });

  bool get _isImage {
    final lower = fileName.toLowerCase();
    return lower.endsWith('.jpg') ||
        lower.endsWith('.jpeg') ||
        lower.endsWith('.png') ||
        lower.endsWith('.gif') ||
        lower.endsWith('.webp');
  }

  @override
  Widget build(BuildContext context) {
    final color = isOwn ? Colors.white : Theme.of(context).colorScheme.onSurface;

    if (_isImage && fileUrl.isNotEmpty) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Image.network(
          fileUrl,
          width: 200,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => _fallback(color),
        ),
      );
    }

    return _fallback(color);
  }

  Widget _fallback(Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.attach_file, color: color, size: 18),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            fileName,
            style: TextStyle(color: color, decoration: TextDecoration.underline),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}
