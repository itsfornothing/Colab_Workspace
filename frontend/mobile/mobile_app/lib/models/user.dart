class User {
  final String id;
  final String email;
  final String fullName;
  final String? jobTitle;
  final String? bio;
  final String? avatarUrl;

  User({
    required this.id,
    required this.email,
    required this.fullName,
    this.jobTitle,
    this.bio,
    this.avatarUrl,
  });

  factory User.fromJson(Map<String, dynamic> json) => User(
        // login response uses 'id'; profile endpoint uses 'user_id'
        id: (json['user_id'] ?? json['id'])?.toString() ?? '',
        email: json['email'] ?? '',
        fullName: json['full_name'] ?? json['name'] ?? '',
        jobTitle: json['job_title'],
        bio: json['bio'],
        avatarUrl: json['avatar_url'] ?? json['profile_picture'] ?? json['profile_url'],
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'full_name': fullName,
        'job_title': jobTitle,
        'bio': bio,
        'avatar_url': avatarUrl,
      };
}
