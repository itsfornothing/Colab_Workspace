class Document {
  final String id;
  final String title;
  final String? content;
  final String workspaceId;
  final String? lastEditedBy;
  final DateTime? lastEditedAt;
  final List<String> collaboratorAvatars;

  Document({
    required this.id,
    required this.title,
    this.content,
    required this.workspaceId,
    this.lastEditedBy,
    this.lastEditedAt,
    this.collaboratorAvatars = const [],
  });

  factory Document.fromJson(Map<String, dynamic> json) => Document(
        id: json['id']?.toString() ?? '',
        title: json['title'] ?? 'Untitled',
        content: json['content'],
        workspaceId: json['workspace_id']?.toString() ?? '',
        lastEditedBy: json['last_edited_by'],
        lastEditedAt: DateTime.tryParse(json['last_edited_at'] ?? ''),
        collaboratorAvatars: List<String>.from(json['collaborator_avatars'] ?? []),
      );
}
