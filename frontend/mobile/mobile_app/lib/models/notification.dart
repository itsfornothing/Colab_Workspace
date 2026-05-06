class AppNotification {
  final String id;
  final String type; // message, invite, mention, system
  final String title;
  final String body;
  final bool isRead;
  final DateTime createdAt;
  final Map<String, dynamic>? data;

  AppNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    required this.isRead,
    required this.createdAt,
    this.data,
  });

  factory AppNotification.fromJson(Map<String, dynamic> json) => AppNotification(
        id: json['id']?.toString() ?? '',
        type: json['type'] ?? 'system',
        title: json['title'] ?? '',
        body: json['body'] ?? '',
        isRead: json['is_read'] ?? false,
        createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
        data: json['data'],
      );
}
