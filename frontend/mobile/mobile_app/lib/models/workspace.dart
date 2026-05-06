class Workspace {
  final String id;
  final String name;
  final String? description;
  final String? avatarUrl;
  final int memberCount;

  Workspace({
    required this.id,
    required this.name,
    this.description,
    this.avatarUrl,
    this.memberCount = 0,
  });

  factory Workspace.fromJson(Map<String, dynamic> json) => Workspace(
        id: json['id']?.toString() ?? '',
        name: json['name'] ?? '',
        description: json['description'],
        avatarUrl: json['avatar_url'],
        memberCount: json['member_count'] ?? 0,
      );
}

class Channel {
  final String id;
  final String name;
  final bool isPrivate;
  final bool isArchived;
  final String? lastMessage;
  final String? lastMessageTime;
  final int unreadCount;
  final int onlineCount;

  Channel({
    required this.id,
    required this.name,
    this.isPrivate = false,
    this.isArchived = false,
    this.lastMessage,
    this.lastMessageTime,
    this.unreadCount = 0,
    this.onlineCount = 0,
  });

  factory Channel.fromJson(Map<String, dynamic> json) => Channel(
        id: json['id']?.toString() ?? '',
        name: json['name'] ?? '',
        isPrivate: json['is_private'] ?? false,
        isArchived: json['is_archived'] ?? false,
        lastMessage: json['last_message'],
        lastMessageTime: json['last_message_time'],
        unreadCount: json['unread_count'] ?? 0,
        onlineCount: json['online_count'] ?? 0,
      );
}

class WorkspaceMember {
  final String id;
  final String email;
  final String fullName;
  final String? avatarUrl;
  final String role;

  WorkspaceMember({
    required this.id,
    required this.email,
    required this.fullName,
    this.avatarUrl,
    required this.role,
  });

  factory WorkspaceMember.fromJson(Map<String, dynamic> json) => WorkspaceMember(
        id: json['id']?.toString() ?? '',
        email: json['email'] ?? '',
        fullName: json['full_name'] ?? '',
        avatarUrl: json['avatar_url'],
        role: json['role'] ?? 'member',
      );
}
