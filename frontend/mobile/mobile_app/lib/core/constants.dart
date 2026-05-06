class AppConstants {
  // Base URLs - Updated to use your computer's IP address for mobile testing
  // Your IP: 10.2.68.2 (change if your IP changes)
  // Port mapping: user-service:8001, chat:8002, collaboration:8003, media:8004, notification:8005, workspace:8000
  static const String baseUrl = 'http://10.2.68.2:8001';  // user-service
  static const String chatBaseUrl = 'http://10.2.68.2:8002';  // chat-service
  static const String workspaceBaseUrl = 'http://10.2.68.2:8000';  // workspace-service
  static const String notificationBaseUrl = 'http://10.2.68.2:8005';  // notification-service
  static const String collabBaseUrl = 'http://10.2.68.2:8003';  // collaboration-service

  static const String apiBase = '$baseUrl/api';
  static const String chatApiBase = '$chatBaseUrl/api';
  static const String workspaceApiBase = '$workspaceBaseUrl/api';
  static const String notificationApiBase = '$notificationBaseUrl/api';
  static const String collabApiBase = '$collabBaseUrl/api';

  static const String wsBase = 'ws://10.2.68.2:8002/ws';  // chat-service
  static const String collabWsBase = 'ws://10.2.68.2:8003/ws';  // collaboration-service
  static const String notifWsBase = 'ws://10.2.68.2:8005/ws';  // notification-service

  // WebSocket host/port for explicit Uri construction (avoids URI parsing issues on iOS)
  static const String wsHost = '10.2.68.2';
  static const int    collabWsPort = 8003;

  // Auth endpoints (user_service :8000)
  static const String loginUrl = '$apiBase/auth/login/';
  static const String registerUrl = '$apiBase/auth/register/';
  static const String refreshUrl = '$apiBase/auth/refresh/';
  static const String logoutUrl = '$apiBase/auth/logout/';
  static const String profileUrl = '$apiBase/auth/profile/';
  static const String profileUpdateUrl = '$apiBase/auth/profile/update/';
  static const String passwordResetUrl = '$apiBase/auth/password/reset/';
  static const String passwordChangeUrl = '$apiBase/auth/password/change/';
  static const String sessionsUrl = '$apiBase/auth/sessions/';
  static String sessionUrl(String id) => '$apiBase/auth/sessions/$id/';
  static const String notificationPrefsUrl = '$apiBase/auth/notification-preferences/';
  static const String fcmTokenUrl = '$apiBase/auth/profile/fcm-token/';
  static const String userSearchUrl = '$apiBase/users/';

  // Chat service endpoints (:8002)
  static const String channelsUrl = '$chatApiBase/channels/';
  static const String discoverChannelsUrl = '$chatApiBase/channels/discover/';
  static String joinChannelUrl(String id) => '$chatApiBase/channels/$id/join/';
  static String leaveChannelUrl(String id) => '$chatApiBase/channels/$id/leave/';
  static String channelMessagesUrl(String id) => '$chatApiBase/channels/$id/messages/';
  static String channelUploadUrl(String id) => '$chatApiBase/channels/$id/upload/';
  static const String chatUserSearchUrl = '$chatApiBase/users/search/';
  static const String dmConversationsUrl = '$chatApiBase/dm/';
  static const String startDmUrl = '$chatApiBase/dm/start/';
  static String dmMessagesUrl(String id) => '$chatApiBase/dm/$id/messages/';
  static String sendDmUrl(String id) => '$chatApiBase/dm/$id/send/';
  static String dmUploadUrl(String id) => '$chatApiBase/dm/$id/upload/';

  // Workspace service endpoints (:8003)
  static const String workspacesUrl = '$workspaceApiBase/workspaces/';
  static const String workspacesListUrl = '$workspaceApiBase/workspaces/list/';
  static const String workspaceSwitchUrl = '$workspaceApiBase/workspaces/switch/';
  static String workspaceUrl(String id) => '$workspaceApiBase/workspaces/$id/';
  static String deleteWorkspaceUrl(String id) => '$workspaceApiBase/workspaces/$id/';
  static String leaveWorkspaceUrl(String id) => '$workspaceApiBase/workspaces/$id/leave/';
  static String workspaceMembersUrl(String id) => '$workspaceApiBase/workspaces/$id/members/';
  static String membershipUrl(String id) => '$workspaceApiBase/memberships/$id/';
  static String workspaceChannelsUrl(String id) => '$workspaceApiBase/workspaces/$id/channels/';
  static String workspaceDocumentsUrl(String id) => '$collabApiBase/documents/list/?workspace_id=$id';
  static String workspaceTeamsUrl(String id) => '$workspaceApiBase/workspaces/$id/teams/';
  static String workspaceInviteLinkUrl(String id) => '$workspaceApiBase/workspaces/$id/invites/';
  static const String inviteUserUrl = '$workspaceApiBase/invitations/';
  static const String acceptInvitationUrl = '$workspaceApiBase/invitations/accept/';
  static const String joinByLinkUrl = '$workspaceApiBase/invitations/join/';

  // Collaboration service endpoints (:8005)
  static const String documentsUrl = '$collabApiBase/documents/';
  static String documentUrl(String id) => '$collabApiBase/documents/$id/';
  static String documentUpdateUrl(String id) => '$collabApiBase/documents/$id/update/';
  static String documentArchiveUrl(String id) => '$collabApiBase/documents/$id/archive/';
  static String documentVersionsUrl(String id) => '$collabApiBase/documents/$id/versions/';
  static const String tasksUrl = '$collabApiBase/tasks/';
  static String taskUrl(String id) => '$collabApiBase/tasks/$id/';
  static const String filesUrl = '$collabApiBase/files/';
  static const String fileUploadUrl = '$collabApiBase/files/upload/';
  static String fileDeleteUrl(String id) => '$collabApiBase/files/$id/';

  // Notification service endpoints (:8005)
  static const String notificationsUrl = '$notificationApiBase/notifications/';
  static const String markReadUrl = '$notificationApiBase/notifications/mark-all-read/';
  static String markOneReadUrl(String id) => '$notificationApiBase/notifications/$id/read/';
  static const String notificationServicePrefsUrl = '$notificationApiBase/notifications/preferences/';

  // Room endpoints (chat-service :8002)
  static const String roomsUrl = '$chatApiBase/rooms/';
  static const String iceServersUrl = '$chatApiBase/ice-servers/';

  // Invitation
  static const String invitationsUrl = '$workspaceApiBase/invitations/';

  // ── WebSocket URL validation helpers ────────────────────────────────────

  /// Validates that a WebSocket URL uses the correct ws:// or wss:// scheme.
  /// Throws an [AssertionError] in debug mode if the scheme is incorrect.
  /// Returns the URL unchanged if valid.
  static String validateWsUrl(String url) {
    assert(
      url.startsWith('ws://') || url.startsWith('wss://'),
      'WebSocket URL must use ws:// or wss:// scheme. Got: $url',
    );
    return url;
  }

  /// Validates that a WebSocket URI uses the correct ws:// or wss:// scheme.
  static Uri validateWsUri(Uri uri) {
    assert(
      uri.scheme == 'ws' || uri.scheme == 'wss',
      'WebSocket URI must use ws:// or wss:// scheme. Got: ${uri.scheme}://',
    );
    return uri;
  }

  // ── WebSocket endpoints ──────────────────────────────────────────────────

  static String chatWs(String channelId, String token) =>
      validateWsUrl('$wsBase/chat/$channelId/?token=$token');
  static String docsWs(String documentId, String token) =>
      validateWsUrl('$collabWsBase/docs/$documentId/?token=$token');
  static String webrtcWs(String roomId, String token) =>
      // Chat service routing.py has: re_path(r"^ws/calls/$", CallConsumer.as_asgi())
      // CallConsumer is a personal signaling channel — room_id goes in message bodies.
      validateWsUrl('$wsBase/calls/?token=$token');
  static String notificationsWs(String token) =>
      validateWsUrl('$notifWsBase/notifications/?token=$token');

  // Storage keys
  static const String accessTokenKey = 'access_token';
  static const String refreshTokenKey = 'refresh_token';
  static const String userIdKey = 'user_id';
  static const String userEmailKey = 'user_email';
  static const String workspaceIdKey = 'current_workspace_id';
}
