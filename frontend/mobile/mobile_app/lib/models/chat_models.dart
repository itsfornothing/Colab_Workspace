class ChatUser {
  final String id;
  final String username;
  final String fullName;
  final String? profilePicture;

  const ChatUser({
    required this.id,
    required this.username,
    required this.fullName,
    this.profilePicture,
  });

  factory ChatUser.fromJson(Map<String, dynamic> j) => ChatUser(
        id: j['id']?.toString() ?? '',
        username: j['username'] ?? '',
        fullName: j['full_name'] ?? j['username'] ?? '',
        profilePicture: j['profile_picture'],
      );

  String get displayName => fullName.isNotEmpty ? fullName : username;

  String get initial {
    final src = displayName;
    return src.isNotEmpty ? src[0].toUpperCase() : '?';
  }
}

class ChatChannel {
  final String id;
  final String name;
  final bool isPrivate;
  final String description;
  final int memberCount;
  final bool isJoined;

  const ChatChannel({
    required this.id,
    required this.name,
    required this.isPrivate,
    this.description = '',
    this.memberCount = 0,
    this.isJoined = false,
  });

  factory ChatChannel.fromJson(Map<String, dynamic> j) => ChatChannel(
        id: j['id']?.toString() ?? '',
        name: j['name'] ?? '',
        isPrivate: j['is_private'] ?? false,
        description: j['description'] ?? '',
        memberCount: j['member_count'] ?? 0,
        isJoined: j['is_joined'] ?? false,
      );
}

class ChatMessage {
  final String id;
  final String? channelId;
  final String? conversationId;
  final ChatUser sender;
  final String content;
  final String messageType;
  final String? fileUrl;
  final String? fileName;
  final bool isEdited;
  final bool isDeleted;
  final DateTime createdAt;

  const ChatMessage({
    required this.id,
    this.channelId,
    this.conversationId,
    required this.sender,
    required this.content,
    this.messageType = 'text',
    this.fileUrl,
    this.fileName,
    this.isEdited = false,
    this.isDeleted = false,
    required this.createdAt,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
        id: j['id']?.toString() ?? '',
        channelId: j['channel_id']?.toString(),
        conversationId: j['conversation_id']?.toString(),
        sender: ChatUser.fromJson(j['sender'] ?? {}),
        content: j['content'] ?? '',
        messageType: j['message_type'] ?? 'text',
        fileUrl: j['file_url'],
        fileName: j['file_name'],
        isEdited: j['is_edited'] ?? false,
        isDeleted: j['is_deleted'] ?? false,
        createdAt: DateTime.tryParse(j['created_at'] ?? '') ?? DateTime.now(),
      );

  bool get isFile => messageType == 'file';
}

class DmConversation {
  final String id;
  final ChatUser otherUser;
  final String? lastMessage;
  final DateTime? lastMessageTime;

  const DmConversation({
    required this.id,
    required this.otherUser,
    this.lastMessage,
    this.lastMessageTime,
  });

  factory DmConversation.fromJson(Map<String, dynamic> j) => DmConversation(
        id: j['id']?.toString() ?? '',
        otherUser: ChatUser.fromJson(j['other_user'] ?? {}),
        lastMessage: j['last_message'],
        lastMessageTime: j['last_message_time'] != null
            ? DateTime.tryParse(j['last_message_time'])
            : null,
      );
}
