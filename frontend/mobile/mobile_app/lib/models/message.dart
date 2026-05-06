class Message {
  final String id;
  final String channelId;
  final String userId;
  final String username;
  final String? userAvatar;
  final String content;
  final DateTime timestamp;
  final bool isDeleted;
  final bool isEdited;
  final List<Reaction> reactions;
  final String? fileUrl;
  final String? fileName;

  Message({
    required this.id,
    required this.channelId,
    required this.userId,
    required this.username,
    this.userAvatar,
    required this.content,
    required this.timestamp,
    this.isDeleted = false,
    this.isEdited = false,
    this.reactions = const [],
    this.fileUrl,
    this.fileName,
  });

  factory Message.fromJson(Map<String, dynamic> json) => Message(
        id: json['id']?.toString() ?? '',
        channelId: json['channel_id']?.toString() ?? '',
        userId: json['user_id']?.toString() ?? json['user']?['id']?.toString() ?? '',
        username: json['username'] ?? json['user']?['full_name'] ?? 'Unknown',
        userAvatar: json['user_avatar'] ?? json['user']?['avatar_url'],
        content: json['content'] ?? '',
        timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
        isDeleted: json['is_deleted'] ?? false,
        isEdited: json['is_edited'] ?? false,
        reactions: (json['reactions'] as List<dynamic>?)
                ?.map((r) => Reaction.fromJson(r))
                .toList() ??
            [],
        fileUrl: json['file_url'],
        fileName: json['file_name'],
      );

  Message copyWith({
    String? content,
    bool? isDeleted,
    bool? isEdited,
    List<Reaction>? reactions,
  }) =>
      Message(
        id: id,
        channelId: channelId,
        userId: userId,
        username: username,
        userAvatar: userAvatar,
        content: content ?? this.content,
        timestamp: timestamp,
        isDeleted: isDeleted ?? this.isDeleted,
        isEdited: isEdited ?? this.isEdited,
        reactions: reactions ?? this.reactions,
        fileUrl: fileUrl,
        fileName: fileName,
      );
}

class Reaction {
  final String emoji;
  final int count;
  final List<String> userIds;

  Reaction({required this.emoji, required this.count, required this.userIds});

  factory Reaction.fromJson(Map<String, dynamic> json) => Reaction(
        emoji: json['emoji'] ?? '',
        count: json['count'] ?? 0,
        userIds: List<String>.from(json['user_ids'] ?? []),
      );
}
