import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../core/constants.dart';
import '../models/notification.dart';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

class NotificationState {
  final int unreadCount;
  final List<AppNotification> notifications;
  final bool isLoading;
  final String? error;

  const NotificationState({
    this.unreadCount = 0,
    this.notifications = const [],
    this.isLoading = false,
    this.error,
  });

  NotificationState copyWith({
    int? unreadCount,
    List<AppNotification>? notifications,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return NotificationState(
      unreadCount: unreadCount ?? this.unreadCount,
      notifications: notifications ?? this.notifications,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

// ---------------------------------------------------------------------------
// Notifier
// ---------------------------------------------------------------------------

class NotificationNotifier extends StateNotifier<NotificationState> {
  final ApiClient _api;

  NotificationNotifier({ApiClient? api})
      : _api = api ?? ApiClient(),
        super(const NotificationState());

  /// Fetch up to 20 notifications from the backend.
  /// Sets [isLoading] while the request is in flight.
  /// On success, updates [notifications] and recalculates [unreadCount].
  /// On failure, sets [error].
  Future<void> fetchNotifications() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final response = await _api.get(
        '${AppConstants.notificationsUrl}?limit=20',
      );
      if (response.statusCode == 200) {
        final Map<String, dynamic> jsonMap =
            jsonDecode(response.body) as Map<String, dynamic>;
        final List<dynamic> jsonList = jsonMap['results'] as List<dynamic>;
        final notifications = jsonList
            .map((e) => AppNotification.fromJson(e as Map<String, dynamic>))
            .toList();
        final int serverUnreadCount =
            (jsonMap['unread_count'] as num?)?.toInt() ??
            notifications.where((n) => !n.isRead).length;
        state = state.copyWith(
          notifications: notifications,
          unreadCount: serverUnreadCount,
          isLoading: false,
          clearError: true,
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          error: 'Failed to load notifications (${response.statusCode}).',
        );
      }
    } catch (e) {
      final msg = e.toString();
      final isConnectivity = e is SocketException || e is TimeoutException;
      final isAuthError = msg.contains('Session expired') || msg.contains('401');
      state = state.copyWith(
        isLoading: false,
        error: isConnectivity
            ? 'Notification service is currently unavailable. Please try again later.'
            : isAuthError
                ? 'Session expired. Please log in again.'
                : 'Could not connect to server. Check your connection.',
      );
    }
  }

  /// Optimistically mark all notifications as read and POST to the backend.
  /// Sets [unreadCount] to 0 and flips every notification's [isRead] to true.
  void markAllRead() {
    final updated = state.notifications
        .map((n) => AppNotification(
              id: n.id,
              type: n.type,
              title: n.title,
              body: n.body,
              isRead: true,
              createdAt: n.createdAt,
              data: n.data,
            ))
        .toList();
    state = state.copyWith(
      notifications: updated,
      unreadCount: 0,
    );
    // Fire-and-forget POST — failure is non-critical; next fetch will reconcile.
    _api.post(AppConstants.markReadUrl, {});
  }

  /// Prepend a notification received via WebSocket.
  /// Increments [unreadCount] by 1 if the notification is unread.
  void addNotification(AppNotification n) {
    final updated = [n, ...state.notifications];
    state = state.copyWith(
      notifications: updated,
      unreadCount: state.unreadCount + (n.isRead ? 0 : 1),
    );
  }

  /// Recompute [unreadCount] from the current [notifications] list.
  void _recalcUnread() {
    state = state.copyWith(
      unreadCount: state.notifications.where((n) => !n.isRead).length,
    );
  }

  // ---------------------------------------------------------------------------
  // Test helpers
  // ---------------------------------------------------------------------------

  /// Seeds the notifier with a pre-built list of notifications.
  ///
  /// **For use in tests only.** This bypasses the network fetch so that
  /// property tests can construct arbitrary initial states without mocking HTTP.
  @visibleForTesting
  void seedForTest(List<AppNotification> notifications) {
    state = NotificationState(
      notifications: List.unmodifiable(notifications),
      unreadCount: notifications.where((n) => !n.isRead).length,
      isLoading: false,
      error: null,
    );
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

final notificationProvider =
    StateNotifierProvider<NotificationNotifier, NotificationState>(
  (ref) => NotificationNotifier(),
);
