// Provider test for NotificationNotifier
//
// Property 1: Bug Condition — Service-Unavailable Error Message
// For any SocketException or TimeoutException thrown by fetchNotifications(),
// the error state must equal the service-unavailable string.
// Validates: Requirements 2.1, 2.2, 2.3
//
// Property 2: Preservation — Generic Error Message for Other Exceptions
// For any exception that is NOT a SocketException or TimeoutException,
// the error state must equal the generic connectivity string.
// Validates: Requirements 3.1
//
// Property 7: Mark-all-read resets unread count to zero
// For any initial NotificationState with any list of AppNotification objects
// (with random isRead values), calling NotificationNotifier.markAllRead()
// shall result in:
//   - state.unreadCount == 0
//   - every notification in state.notifications has isRead == true
// Validates: Requirements 7.4, 9.4
//
// Property 8: Notification list unread count invariant
// For any NotificationState, unreadCount shall equal the number of
// AppNotification items in notifications where isRead == false. This invariant
// must hold after every state mutation: fetch, WebSocket push, and mark-all-read.
// Validates: Requirements 8.7, 9.2

import 'dart:async';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart' hide test, group, expect, isTrue, isEmpty, equals;
import 'package:glados/glados.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/api_client.dart';
import 'package:mobile_app/models/notification.dart';
import 'package:mobile_app/providers/notification_provider.dart';

// ---------------------------------------------------------------------------
// Arbitrary generators for AppNotification
// ---------------------------------------------------------------------------

extension AnyAppNotification on Any {
  /// Generates a random [AppNotification] with a random [isRead] value.
  Generator<AppNotification> get appNotification => combine4(
        any.nonEmptyLetterOrDigits,
        any.nonEmptyLetterOrDigits,
        any.nonEmptyLetterOrDigits,
        any.bool,
        (id, title, body, isRead) => AppNotification(
          id: id,
          type: 'system',
          title: title,
          body: body,
          isRead: isRead,
          createdAt: DateTime(2024, 1, 1),
        ),
      );

  /// Generates a list of 0–20 [AppNotification] objects with random [isRead].
  Generator<List<AppNotification>> get appNotificationList =>
      any.listWithLengthInRange(0, 20, any.appNotification);
}

// ---------------------------------------------------------------------------
// No-op ApiClient — post is a no-op, get is not overridden
// ---------------------------------------------------------------------------

class _NoOpApiClient extends ApiClient {
  _NoOpApiClient() : super.internal();

  @override
  Future<http.Response> post(
    String url,
    Map<String, dynamic> body, {
    bool auth = true,
  }) async =>
      http.Response('{}', 200);
}

// ---------------------------------------------------------------------------
// Throwing mock ApiClient — get throws a caller-supplied exception
// ---------------------------------------------------------------------------

class _ThrowingApiClient extends ApiClient {
  final Object exception;

  _ThrowingApiClient(this.exception) : super.internal();

  @override
  Future<http.Response> get(String url) => Future.error(exception);

  @override
  Future<http.Response> post(
    String url,
    Map<String, dynamic> body, {
    bool auth = true,
  }) async =>
      http.Response('{}', 200);
}

// ---------------------------------------------------------------------------
// Configurable mock ApiClient — get returns a fixed status + body
// ---------------------------------------------------------------------------

class _MockApiClient extends ApiClient {
  final int getStatusCode;
  final String getBody;

  _MockApiClient({required this.getStatusCode, required this.getBody})
      : super.internal();

  @override
  Future<http.Response> get(String url) async =>
      http.Response(getBody, getStatusCode);

  @override
  Future<http.Response> post(
    String url,
    Map<String, dynamic> body, {
    bool auth = true,
  }) async =>
      http.Response('{}', 200);
}

// ---------------------------------------------------------------------------
// Completer-based mock ApiClient — get waits on a Completer
// ---------------------------------------------------------------------------

class _CompleterApiClient extends ApiClient {
  final Completer<http.Response> _completer;

  _CompleterApiClient(this._completer) : super.internal();

  @override
  Future<http.Response> get(String url) => _completer.future;

  @override
  Future<http.Response> post(
    String url,
    Map<String, dynamic> body, {
    bool auth = true,
  }) async =>
      http.Response('{}', 200);
}

// ---------------------------------------------------------------------------
// Helper: build a NotificationNotifier pre-seeded with a given list
// ---------------------------------------------------------------------------

NotificationNotifier _notifierWithNotifications(
    List<AppNotification> notifications) {
  final notifier = NotificationNotifier(api: _NoOpApiClient());
  notifier.seedForTest(notifications);
  return notifier;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  // =========================================================================
  // Property 7: mark-all-read resets unread count to zero
  // Validates: Requirements 7.4, 9.4
  // =========================================================================

  group('NotificationNotifier — Property 7: mark-all-read resets unread count',
      () {
    Glados(any.appNotificationList).test(
      'markAllRead() sets unreadCount to 0 and all notifications to isRead=true',
      (notifications) {
        final notifier = _notifierWithNotifications(notifications);

        final initialUnread = notifications.where((n) => !n.isRead).length;
        expect(notifier.state.unreadCount, equals(initialUnread),
            reason: 'Pre-condition: unreadCount must equal count of unread items');

        notifier.markAllRead();

        expect(notifier.state.unreadCount, equals(0),
            reason: 'After markAllRead(), unreadCount must be 0');

        for (final n in notifier.state.notifications) {
          expect(n.isRead, isTrue,
              reason:
                  'After markAllRead(), every notification must have isRead=true '
                  '(failed for notification id="${n.id}")');
        }

        expect(notifier.state.notifications.length, equals(notifications.length),
            reason: 'markAllRead() must not add or remove notifications');
      },
    );

    test('markAllRead() on empty list leaves unreadCount at 0', () {
      final notifier = _notifierWithNotifications([]);
      notifier.markAllRead();
      expect(notifier.state.unreadCount, equals(0));
      expect(notifier.state.notifications, isEmpty);
    });

    test('markAllRead() when all notifications are already read', () {
      final allRead = List.generate(
        5,
        (i) => AppNotification(
          id: 'n$i', type: 'system', title: 'Title $i',
          body: 'Body $i', isRead: true, createdAt: DateTime(2024, 1, 1),
        ),
      );
      final notifier = _notifierWithNotifications(allRead);
      notifier.markAllRead();
      expect(notifier.state.unreadCount, equals(0));
      for (final n in notifier.state.notifications) {
        expect(n.isRead, isTrue);
      }
    });

    test('markAllRead() when all notifications are unread', () {
      final allUnread = List.generate(
        5,
        (i) => AppNotification(
          id: 'n$i', type: 'system', title: 'Title $i',
          body: 'Body $i', isRead: false, createdAt: DateTime(2024, 1, 1),
        ),
      );
      final notifier = _notifierWithNotifications(allUnread);
      expect(notifier.state.unreadCount, equals(5));
      notifier.markAllRead();
      expect(notifier.state.unreadCount, equals(0));
      for (final n in notifier.state.notifications) {
        expect(n.isRead, isTrue);
      }
    });

    test('markAllRead() when notifications have mixed isRead values', () {
      final mixed = [
        AppNotification(id: 'a', type: 'system', title: 'A', body: '',
            isRead: false, createdAt: DateTime(2024, 1, 1)),
        AppNotification(id: 'b', type: 'system', title: 'B', body: '',
            isRead: true, createdAt: DateTime(2024, 1, 1)),
        AppNotification(id: 'c', type: 'system', title: 'C', body: '',
            isRead: false, createdAt: DateTime(2024, 1, 1)),
      ];
      final notifier = _notifierWithNotifications(mixed);
      expect(notifier.state.unreadCount, equals(2));
      notifier.markAllRead();
      expect(notifier.state.unreadCount, equals(0));
      for (final n in notifier.state.notifications) {
        expect(n.isRead, isTrue);
      }
    });

    test('markAllRead() is idempotent — calling twice still yields unreadCount=0',
        () {
      final notifications = List.generate(
        3,
        (i) => AppNotification(
          id: 'n$i', type: 'system', title: 'T$i',
          body: '', isRead: false, createdAt: DateTime(2024, 1, 1),
        ),
      );
      final notifier = _notifierWithNotifications(notifications);
      notifier.markAllRead();
      notifier.markAllRead();
      expect(notifier.state.unreadCount, equals(0));
      for (final n in notifier.state.notifications) {
        expect(n.isRead, isTrue);
      }
    });
  });

  // =========================================================================
  // Property 8: unread count invariant after every mutation
  // Validates: Requirements 8.7, 9.2
  // =========================================================================

  group(
      'NotificationNotifier — Property 8: unread count invariant after every mutation',
      () {
    Glados2(any.appNotificationList, any.appNotificationList).test(
      'invariant holds after replacing list (simulated fetch)',
      (initial, fetched) {
        final notifier = _notifierWithNotifications(initial);
        notifier.seedForTest(fetched);
        expect(
          notifier.state.unreadCount,
          equals(notifier.state.notifications.where((n) => !n.isRead).length),
          reason: 'After fetch mutation, unreadCount must equal count of unread items',
        );
      },
    );

    Glados2(any.appNotificationList, any.appNotification).test(
      'invariant holds after addNotification (WebSocket push)',
      (initial, newNotif) {
        final notifier = _notifierWithNotifications(initial);
        notifier.addNotification(newNotif);
        expect(
          notifier.state.unreadCount,
          equals(notifier.state.notifications.where((n) => !n.isRead).length),
          reason: 'After addNotification, unreadCount must equal count of unread items',
        );
      },
    );

    Glados(any.appNotificationList).test(
      'invariant holds after markAllRead',
      (initial) {
        final notifier = _notifierWithNotifications(initial);
        notifier.markAllRead();
        expect(
          notifier.state.unreadCount,
          equals(notifier.state.notifications.where((n) => !n.isRead).length),
          reason: 'After markAllRead, unreadCount must equal count of unread items (should be 0)',
        );
      },
    );

    Glados2(any.appNotificationList, any.appNotification).test(
      'invariant holds after a sequence of mutations (add → markAllRead → fetch)',
      (initial, newNotif) {
        final notifier = _notifierWithNotifications(initial);

        notifier.addNotification(newNotif);
        expect(notifier.state.unreadCount,
            equals(notifier.state.notifications.where((n) => !n.isRead).length),
            reason: 'Invariant must hold after addNotification');

        notifier.markAllRead();
        expect(notifier.state.unreadCount,
            equals(notifier.state.notifications.where((n) => !n.isRead).length),
            reason: 'Invariant must hold after markAllRead');

        notifier.seedForTest(initial);
        expect(notifier.state.unreadCount,
            equals(notifier.state.notifications.where((n) => !n.isRead).length),
            reason: 'Invariant must hold after fetch (seedForTest)');
      },
    );

    test('invariant holds on initial empty state', () {
      final notifier = _notifierWithNotifications([]);
      expect(notifier.state.unreadCount,
          equals(notifier.state.notifications.where((n) => !n.isRead).length));
    });

    test('invariant holds after adding an unread notification to empty list', () {
      final notifier = _notifierWithNotifications([]);
      notifier.addNotification(AppNotification(
        id: 'x1', type: 'system', title: 'New', body: 'Body',
        isRead: false, createdAt: DateTime(2024, 1, 1),
      ));
      expect(notifier.state.unreadCount,
          equals(notifier.state.notifications.where((n) => !n.isRead).length));
      expect(notifier.state.unreadCount, equals(1));
    });

    test('invariant holds after adding a read notification', () {
      final notifier = _notifierWithNotifications([]);
      notifier.addNotification(AppNotification(
        id: 'x2', type: 'system', title: 'Already read', body: 'Body',
        isRead: true, createdAt: DateTime(2024, 1, 1),
      ));
      expect(notifier.state.unreadCount,
          equals(notifier.state.notifications.where((n) => !n.isRead).length));
      expect(notifier.state.unreadCount, equals(0));
    });

    test('invariant holds after multiple addNotification calls', () {
      final notifier = _notifierWithNotifications([]);
      for (var i = 0; i < 5; i++) {
        notifier.addNotification(AppNotification(
          id: 'n$i', type: 'system', title: 'N$i', body: '',
          isRead: i.isEven, createdAt: DateTime(2024, 1, 1),
        ));
        expect(notifier.state.unreadCount,
            equals(notifier.state.notifications.where((n) => !n.isRead).length),
            reason: 'Invariant must hold after adding notification $i');
      }
    });
  });

  // =========================================================================
  // Property 9: WebSocket notification prepend increments unread count
  // Validates: Requirements 8.5, 9.3
  // =========================================================================

  group(
      'NotificationNotifier — Property 9: WebSocket notification prepend increments unread count',
      () {
    Glados2(any.appNotificationList, any.appNotification).test(
      'addNotification(n) with unread n increments unreadCount by 1 and prepends n',
      (initialList, newNotif) {
        final unreadNotif = AppNotification(
          id: newNotif.id, type: newNotif.type, title: newNotif.title,
          body: newNotif.body, isRead: false,
          createdAt: newNotif.createdAt, data: newNotif.data,
        );

        final notifier = _notifierWithNotifications(initialList);
        final initialUnreadCount = notifier.state.unreadCount;

        notifier.addNotification(unreadNotif);

        expect(notifier.state.unreadCount, equals(initialUnreadCount + 1),
            reason: 'After addNotification with an unread notification, '
                'unreadCount must be initial.unreadCount + 1 '
                '(was $initialUnreadCount, got ${notifier.state.unreadCount})');

        expect(notifier.state.notifications, isNotEmpty,
            reason: 'notifications list must not be empty after addNotification');
        expect(notifier.state.notifications[0].id, equals(unreadNotif.id),
            reason: 'The new notification must appear at index 0 of the list');

        expect(notifier.state.notifications.length, equals(initialList.length + 1),
            reason: 'addNotification must prepend exactly one item');
      },
    );

    test('addNotification prepends to empty list and sets unreadCount to 1', () {
      final notifier = _notifierWithNotifications([]);
      final n = AppNotification(
        id: 'ws-1', type: 'message', title: 'New message',
        body: 'Hello!', isRead: false, createdAt: DateTime(2024, 6, 1),
      );
      notifier.addNotification(n);
      expect(notifier.state.unreadCount, equals(1));
      expect(notifier.state.notifications.length, equals(1));
      expect(notifier.state.notifications[0].id, equals('ws-1'));
    });

    test('addNotification prepends to non-empty list and increments unreadCount', () {
      final existing = [
        AppNotification(id: 'old-1', type: 'system', title: 'Old', body: '',
            isRead: false, createdAt: DateTime(2024, 1, 1)),
        AppNotification(id: 'old-2', type: 'system', title: 'Old 2', body: '',
            isRead: true, createdAt: DateTime(2024, 1, 2)),
      ];
      final notifier = _notifierWithNotifications(existing);
      expect(notifier.state.unreadCount, equals(1));

      final newNotif = AppNotification(
        id: 'ws-new', type: 'mention', title: 'You were mentioned',
        body: '@you', isRead: false, createdAt: DateTime(2024, 6, 1),
      );
      notifier.addNotification(newNotif);

      expect(notifier.state.unreadCount, equals(2));
      expect(notifier.state.notifications[0].id, equals('ws-new'));
      expect(notifier.state.notifications.length, equals(3));
    });

    test('addNotification with a read notification does NOT increment unreadCount', () {
      final notifier = _notifierWithNotifications([]);
      final readNotif = AppNotification(
        id: 'ws-read', type: 'system', title: 'Already read',
        body: '', isRead: true, createdAt: DateTime(2024, 6, 1),
      );
      notifier.addNotification(readNotif);
      expect(notifier.state.unreadCount, equals(0));
      expect(notifier.state.notifications[0].id, equals('ws-read'));
    });

    test('addNotification preserves existing notifications after the new one', () {
      final existing = List.generate(
        3,
        (i) => AppNotification(
          id: 'e$i', type: 'system', title: 'Existing $i',
          body: '', isRead: false, createdAt: DateTime(2024, 1, i + 1),
        ),
      );
      final notifier = _notifierWithNotifications(existing);

      final newNotif = AppNotification(
        id: 'ws-latest', type: 'message', title: 'Latest',
        body: '', isRead: false, createdAt: DateTime(2024, 6, 1),
      );
      notifier.addNotification(newNotif);

      expect(notifier.state.notifications[0].id, equals('ws-latest'));
      for (var i = 0; i < existing.length; i++) {
        expect(notifier.state.notifications[i + 1].id, equals(existing[i].id),
            reason: 'Existing notification at original index $i must be at index ${i + 1} after prepend');
      }
    });
  });

  // =========================================================================
  // Unit tests: initial state and fetchNotifications paths
  // Validates: Requirements 9.1, 8.3, 8.4
  // =========================================================================

  group('NotificationNotifier — unit tests: initial state and fetch paths', () {
    test('initial state has correct defaults', () {
      final notifier = NotificationNotifier(api: _NoOpApiClient());
      expect(notifier.state.unreadCount, equals(0),
          reason: 'Initial unreadCount must be 0');
      expect(notifier.state.notifications, isEmpty,
          reason: 'Initial notifications list must be empty');
      expect(notifier.state.isLoading, equals(false),
          reason: 'Initial isLoading must be false');
      expect(notifier.state.error, isNull,
          reason: 'Initial error must be null');
    });

    test('fetchNotifications sets error on HTTP failure (non-200 response)', () async {
      final notifier = NotificationNotifier(
        api: _MockApiClient(
          getStatusCode: 500,
          getBody: '{"detail": "Internal Server Error"}',
        ),
      );
      await notifier.fetchNotifications();
      expect(notifier.state.error, isNotNull,
          reason: 'state.error must be non-null after a non-200 response');
      expect(notifier.state.isLoading, equals(false),
          reason: 'state.isLoading must be false after fetch completes (even on error)');
    });

    test('fetchNotifications sets empty list on empty response (200 + [])', () async {
      final notifier = NotificationNotifier(
        api: _MockApiClient(getStatusCode: 200, getBody: '[]'),
      );
      await notifier.fetchNotifications();
      expect(notifier.state.notifications, isEmpty,
          reason: 'state.notifications must be empty when server returns []');
      expect(notifier.state.error, isNull,
          reason: 'state.error must be null after a successful fetch');
      expect(notifier.state.isLoading, equals(false),
          reason: 'state.isLoading must be false after fetch completes');
      expect(notifier.state.unreadCount, equals(0),
          reason: 'state.unreadCount must be 0 when notifications list is empty');
    });
  });

  // =========================================================================
  // Task 1.3 — Unit tests: fetchNotifications() exception and HTTP error paths
  //
  // Covers: SocketException → service-unavailable message
  //         TimeoutException → service-unavailable message
  //         FormatException → generic message
  //         HTTP 500 → status-code message
  //         HTTP 200 → success
  //
  // Validates: Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3
  // =========================================================================

  group('NotificationNotifier — fetchNotifications() exception and HTTP error paths (Task 1.3)', () {
    const serviceUnavailableMsg =
        'Notification service is currently unavailable. Please try again later.';
    const genericConnectivityMsg =
        'Could not connect to server. Check your connection.';

    // -------------------------------------------------------------------------
    // SocketException → service-unavailable message
    // Requirement 2.1 / 2.2
    // -------------------------------------------------------------------------
    test('SocketException (connection refused) sets service-unavailable error message', () async {
      final notifier = NotificationNotifier(
        api: _ThrowingApiClient(const SocketException('Connection refused')),
      );
      await notifier.fetchNotifications();
      expect(notifier.state.error, equals(serviceUnavailableMsg),
          reason: 'SocketException must produce the service-unavailable message');
      expect(notifier.state.isLoading, equals(false),
          reason: 'isLoading must be false after fetch completes');
    });

    test('SocketException (failed host lookup) sets service-unavailable error message', () async {
      final notifier = NotificationNotifier(
        api: _ThrowingApiClient(
          const SocketException('Failed host lookup: notifications.example.com'),
        ),
      );
      await notifier.fetchNotifications();
      expect(notifier.state.error, equals(serviceUnavailableMsg),
          reason: 'SocketException (host lookup) must produce the service-unavailable message');
    });

    // -------------------------------------------------------------------------
    // TimeoutException → service-unavailable message
    // Requirement 2.3
    // -------------------------------------------------------------------------
    test('TimeoutException sets service-unavailable error message', () async {
      final notifier = NotificationNotifier(
        api: _ThrowingApiClient(
          TimeoutException('Future not completed', const Duration(seconds: 10)),
        ),
      );
      await notifier.fetchNotifications();
      expect(notifier.state.error, equals(serviceUnavailableMsg),
          reason: 'TimeoutException must produce the service-unavailable message');
      expect(notifier.state.isLoading, equals(false),
          reason: 'isLoading must be false after fetch completes');
    });

    // -------------------------------------------------------------------------
    // FormatException → generic connectivity message
    // Requirement 3.1
    // -------------------------------------------------------------------------
    test('FormatException sets generic connectivity error message', () async {
      final notifier = NotificationNotifier(
        api: _ThrowingApiClient(const FormatException('Unexpected character')),
      );
      await notifier.fetchNotifications();
      expect(notifier.state.error, equals(genericConnectivityMsg),
          reason: 'FormatException must produce the generic connectivity message, '
              'not the service-unavailable one');
      expect(notifier.state.isLoading, equals(false),
          reason: 'isLoading must be false after fetch completes');
    });

    // -------------------------------------------------------------------------
    // HTTP 500 → status-code error message
    // Requirement 3.2
    // -------------------------------------------------------------------------
    test('HTTP 500 response sets status-code error message', () async {
      final notifier = NotificationNotifier(
        api: _MockApiClient(
          getStatusCode: 500,
          getBody: '{"detail": "Internal Server Error"}',
        ),
      );
      await notifier.fetchNotifications();
      expect(notifier.state.error, equals('Failed to load notifications (500).'),
          reason: 'HTTP 500 must produce the status-code error message');
      expect(notifier.state.isLoading, equals(false),
          reason: 'isLoading must be false after fetch completes');
    });

    // -------------------------------------------------------------------------
    // HTTP 200 with valid JSON → success, notifications parsed correctly
    // Requirement 3.3
    // -------------------------------------------------------------------------
    test('HTTP 200 with valid JSON parses notifications and clears error', () async {
      const responseBody = '''
[
  {
    "id": "n1",
    "type": "system",
    "title": "Welcome",
    "body": "Welcome to the app!",
    "is_read": false,
    "created_at": "2024-01-01T00:00:00.000Z"
  },
  {
    "id": "n2",
    "type": "mention",
    "title": "You were mentioned",
    "body": "@you in #general",
    "is_read": true,
    "created_at": "2024-01-02T00:00:00.000Z"
  }
]
''';
      final notifier = NotificationNotifier(
        api: _MockApiClient(getStatusCode: 200, getBody: responseBody),
      );
      await notifier.fetchNotifications();

      expect(notifier.state.error, isNull,
          reason: 'state.error must be null after a successful 200 fetch');
      expect(notifier.state.isLoading, equals(false),
          reason: 'isLoading must be false after fetch completes');
      expect(notifier.state.notifications.length, equals(2),
          reason: 'Two notifications must be parsed from the response');
      expect(notifier.state.notifications[0].id, equals('n1'));
      expect(notifier.state.notifications[1].id, equals('n2'));
      // Only n1 is unread
      expect(notifier.state.unreadCount, equals(1),
          reason: 'unreadCount must equal the number of unread notifications');
    });

    // -------------------------------------------------------------------------
    // isLoading lifecycle: true during fetch, false after
    // -------------------------------------------------------------------------
    test('isLoading is set to true during fetch and false after', () async {
      final completer = Completer<http.Response>();
      final notifier = NotificationNotifier(
        api: _CompleterApiClient(completer),
      );

      final fetchFuture = notifier.fetchNotifications();

      expect(notifier.state.isLoading, equals(true),
          reason: 'isLoading must be true while fetch is in flight');

      completer.complete(http.Response('[]', 200));
      await fetchFuture;

      expect(notifier.state.isLoading, equals(false),
          reason: 'isLoading must be false after fetch completes');
    });
  });

  // =========================================================================
  // Task 1.4 — Property-based test: error message classification
  //
  // Property 1: For any SocketException or TimeoutException, the error message
  //             equals the service-unavailable string.
  // Property 2: For all other exceptions, the error message equals the generic
  //             connectivity string.
  //
  // Validates: Requirements 2.1, 2.2, 2.3, 3.1 (Properties 1 and 2)
  // =========================================================================

  group(
    'NotificationNotifier — Properties 1 & 2: error message classification PBT (Task 1.4)',
    () {
      const serviceUnavailableMsg =
          'Notification service is currently unavailable. Please try again later.';
      const genericConnectivityMsg =
          'Could not connect to server. Check your connection.';

      // -----------------------------------------------------------------------
      // Property 1a: any SocketException → service-unavailable
      // -----------------------------------------------------------------------
      Glados(any.nonEmptyLetterOrDigits).test(
        'Property 1a: any SocketException message → service-unavailable error',
        (message) async {
          final notifier = NotificationNotifier(
            api: _ThrowingApiClient(SocketException(message)),
          );
          await notifier.fetchNotifications();
          expect(notifier.state.error, equals(serviceUnavailableMsg),
              reason: 'SocketException("$message") must produce the service-unavailable '
                  'message, not the generic one');
        },
      );

      // -----------------------------------------------------------------------
      // Property 1b: any TimeoutException → service-unavailable
      // -----------------------------------------------------------------------
      Glados(any.nonEmptyLetterOrDigits).test(
        'Property 1b: any TimeoutException message → service-unavailable error',
        (message) async {
          final notifier = NotificationNotifier(
            api: _ThrowingApiClient(TimeoutException(message)),
          );
          await notifier.fetchNotifications();
          expect(notifier.state.error, equals(serviceUnavailableMsg),
              reason: 'TimeoutException("$message") must produce the service-unavailable '
                  'message, not the generic one');
        },
      );

      // -----------------------------------------------------------------------
      // Property 2a: any FormatException → generic connectivity message
      // -----------------------------------------------------------------------
      Glados(any.nonEmptyLetterOrDigits).test(
        'Property 2a: any FormatException message → generic connectivity error',
        (message) async {
          final notifier = NotificationNotifier(
            api: _ThrowingApiClient(FormatException(message)),
          );
          await notifier.fetchNotifications();
          expect(notifier.state.error, equals(genericConnectivityMsg),
              reason: 'FormatException("$message") must produce the generic connectivity '
                  'message, not the service-unavailable one');
        },
      );

      // -----------------------------------------------------------------------
      // Property 2b: any generic Exception → generic connectivity message
      // -----------------------------------------------------------------------
      Glados(any.nonEmptyLetterOrDigits).test(
        'Property 2b: any generic Exception message → generic connectivity error',
        (message) async {
          final notifier = NotificationNotifier(
            api: _ThrowingApiClient(Exception(message)),
          );
          await notifier.fetchNotifications();
          expect(notifier.state.error, equals(genericConnectivityMsg),
              reason: 'Exception("$message") must produce the generic connectivity '
                  'message, not the service-unavailable one');
        },
      );

      // -----------------------------------------------------------------------
      // Cross-checks: messages are mutually exclusive
      // -----------------------------------------------------------------------
      test('FormatException does NOT produce the service-unavailable message', () async {
        final notifier = NotificationNotifier(
          api: _ThrowingApiClient(const FormatException('bad json')),
        );
        await notifier.fetchNotifications();
        expect(notifier.state.error, isNot(equals(serviceUnavailableMsg)),
            reason: 'FormatException must never produce the service-unavailable message');
      });

      test('SocketException does NOT produce the generic connectivity message', () async {
        final notifier = NotificationNotifier(
          api: _ThrowingApiClient(const SocketException('Connection refused')),
        );
        await notifier.fetchNotifications();
        expect(notifier.state.error, isNot(equals(genericConnectivityMsg)),
            reason: 'SocketException must never produce the generic connectivity message');
      });

      test('TimeoutException does NOT produce the generic connectivity message', () async {
        final notifier = NotificationNotifier(
          api: _ThrowingApiClient(TimeoutException('timed out')),
        );
        await notifier.fetchNotifications();
        expect(notifier.state.error, isNot(equals(genericConnectivityMsg)),
            reason: 'TimeoutException must never produce the generic connectivity message');
      });
    },
  );
}
