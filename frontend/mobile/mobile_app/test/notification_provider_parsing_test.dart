// Bug condition exploration test for notification response parsing.
//
// This test encodes the EXPECTED CORRECT behavior after the fix.
// On UNFIXED code it FAILS — that failure confirms the bug condition is
// correctly detected (the provider throws a TypeError when it tries to cast
// the paginated Map response to List<dynamic>, which lands in the generic
// catch branch and sets state.error to the connectivity error string).
//
// On FIXED code this test PASSES.

import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart' hide test, group, expect;
import 'package:glados/glados.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/api_client.dart';
import 'package:mobile_app/models/notification.dart';
import 'package:mobile_app/providers/notification_provider.dart';

// ---------------------------------------------------------------------------
// Mock ApiClient — returns a fixed HTTP 200 with a paginated Map body
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
// Throwing mock — throws an exception instead of returning a response
// ---------------------------------------------------------------------------

class _ThrowingMockApiClient extends ApiClient {
  final Object exception;
  _ThrowingMockApiClient(this.exception) : super.internal();

  @override
  Future<http.Response> get(String url) async => throw exception;

  @override
  Future<http.Response> post(
    String url,
    Map<String, dynamic> body, {
    bool auth = true,
  }) async =>
      http.Response('{}', 200);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('Bug condition exploration', () {
    test('paginated map response does not produce connectivity error', () async {
      final mockApi = _MockApiClient(
        getStatusCode: 200,
        getBody: '{"total":2,"unread_count":1,"results":['
            '{"id":"1","type":"system","title":"Hi","body":"Hello","is_read":false,"created_at":"2026-04-28T10:00:00Z"},'
            '{"id":"2","type":"system","title":"Bye","body":"World","is_read":true,"created_at":"2026-04-28T11:00:00Z"}'
            ']}',
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(notifier.state.error, isNull);
      expect(notifier.state.notifications.length, equals(2));
      expect(notifier.state.unreadCount, equals(1));
    });
  });

  // -------------------------------------------------------------------------
  // Unit tests — all branches of the fixed fetchNotifications()
  // -------------------------------------------------------------------------

  group('Unit tests — fetchNotifications branches', () {
    // 3.1 — HTTP 200 with paginated response containing 2 notifications and unread_count: 1
    test(
        'HTTP 200 with 2 notifications and unread_count:1 → length==2, unreadCount==1, error==null',
        () async {
      final mockApi = _MockApiClient(
        getStatusCode: 200,
        getBody: '{"total":2,"unread_count":1,"results":['
            '{"id":"1","type":"system","title":"T","body":"B","is_read":false,"created_at":"2026-04-28T10:00:00Z"},'
            '{"id":"2","type":"system","title":"T2","body":"B2","is_read":true,"created_at":"2026-04-28T11:00:00Z"}'
            ']}',
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(notifier.state.notifications.length, equals(2));
      expect(notifier.state.unreadCount, equals(1));
      expect(notifier.state.error, isNull);
    });

    // 3.2 — HTTP 200 with empty results and unread_count: 0
    test(
        'HTTP 200 with empty results and unread_count:0 → isEmpty, unreadCount==0',
        () async {
      final mockApi = _MockApiClient(
        getStatusCode: 200,
        getBody: '{"total":0,"unread_count":0,"results":[]}',
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(notifier.state.notifications.isEmpty, isTrue);
      expect(notifier.state.unreadCount, equals(0));
      expect(notifier.state.error, isNull);
    });

    // 3.3 — HTTP 200 with unread_count field absent → falls back to local count
    test(
        'HTTP 200 with unread_count absent → unreadCount falls back to local count of unread items',
        () async {
      final mockApi = _MockApiClient(
        getStatusCode: 200,
        getBody: '{"total":2,"results":['
            '{"id":"1","type":"system","title":"T","body":"B","is_read":false,"created_at":"2026-04-28T10:00:00Z"},'
            '{"id":"2","type":"system","title":"T2","body":"B2","is_read":false,"created_at":"2026-04-28T11:00:00Z"}'
            ']}',
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      // Both items have is_read: false, so local fallback count is 2
      expect(notifier.state.unreadCount, equals(2));
      expect(notifier.state.error, isNull);
    });

    // 3.4 — HTTP 401 response
    test('HTTP 401 → state.error contains "401"', () async {
      final mockApi = _MockApiClient(
        getStatusCode: 401,
        getBody: '{}',
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(notifier.state.error, contains('401'));
    });

    // 3.5 — HTTP 500 response
    test('HTTP 500 → state.error contains "500"', () async {
      final mockApi = _MockApiClient(
        getStatusCode: 500,
        getBody: '{}',
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(notifier.state.error, contains('500'));
    });

    // 3.6 — SocketException thrown during get()
    test(
        'SocketException thrown → state.error == service-unavailable message',
        () async {
      final mockApi = _ThrowingMockApiClient(
        const SocketException('Network unreachable'),
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(
        notifier.state.error,
        equals(
          'Notification service is currently unavailable. Please try again later.',
        ),
      );
    });

    // 3.7 — TimeoutException thrown during get()
    test(
        'TimeoutException thrown → state.error == service-unavailable message',
        () async {
      final mockApi = _ThrowingMockApiClient(
        TimeoutException('Request timed out'),
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(
        notifier.state.error,
        equals(
          'Notification service is currently unavailable. Please try again later.',
        ),
      );
    });

    // 3.8 — TypeError thrown (mock returns plain JSON array [] instead of a Map)
    test(
        'TypeError thrown (body is JSON array []) → state.error does NOT contain service-unavailable',
        () async {
      // The fixed provider does: jsonDecode(response.body) as Map<String, dynamic>
      // When body is '[]', this cast throws a TypeError which lands in the
      // generic catch branch (not connectivity), so the error is the generic message.
      final mockApi = _MockApiClient(
        getStatusCode: 200,
        getBody: '[]',
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(
        notifier.state.error,
        isNot(contains('Notification service is currently unavailable')),
      );
      expect(
        notifier.state.error,
        equals('Could not connect to server. Check your connection.'),
      );
    });

    // 3.9 — Exception message contains "Session expired"
    test(
        'Exception with "Session expired" message → state.error == session-expired message',
        () async {
      final mockApi = _ThrowingMockApiClient(
        Exception('Session expired. Please log in again.'),
      );
      final notifier = NotificationNotifier(api: mockApi);
      await notifier.fetchNotifications();
      expect(
        notifier.state.error,
        equals('Session expired. Please log in again.'),
      );
    });
  });

  // -------------------------------------------------------------------------
  // Property-based tests
  // -------------------------------------------------------------------------

  group('Property-based tests', () {
    // PBT-1 (properties P1 + P5):
    // For any list of AppNotification objects with arbitrary isRead values,
    // if the mock returns them in a paginated envelope with unread_count equal
    // to the count of unread items, then state.unreadCount equals that count.
    //
    // **Validates: Requirements P1 and P5**
    Glados(any.list(any.bool)).test(
      'PBT-1: unreadCount always equals server unread_count for any isRead list',
      (List<bool> isReadList) async {
        final notifications = isReadList.asMap().entries.map((entry) {
          return AppNotification(
            id: 'id_${entry.key}',
            type: 'system',
            title: 'Title',
            body: 'Body',
            isRead: entry.value,
            createdAt: DateTime.parse('2026-01-01T00:00:00Z'),
          );
        }).toList();

        final expectedUnread = isReadList.where((r) => !r).length;
        final n = isReadList.length;

        final resultsJson = notifications
            .map((notif) => '{"id":"${notif.id}","type":"system","title":"Title",'
                '"body":"Body","is_read":${notif.isRead},'
                '"created_at":"2026-01-01T00:00:00Z"}')
            .join(',');

        final body =
            '{"total":$n,"unread_count":$expectedUnread,"results":[$resultsJson]}';

        final mockApi = _MockApiClient(getStatusCode: 200, getBody: body);
        final notifier = NotificationNotifier(api: mockApi);
        await notifier.fetchNotifications();

        expect(notifier.state.error, isNull);
        expect(notifier.state.notifications.length, equals(n));
        expect(notifier.state.unreadCount, equals(expectedUnread));
      },
    );

    // PBT-2 (property P3):
    // For any SocketException or TimeoutException, state.error always equals
    // the service-unavailable string.
    //
    // **Validates: Requirements P3**
    Glados(any.letters).test(
      'PBT-2: SocketException or TimeoutException always yields service-unavailable error',
      (String message) async {
        const expectedError =
            'Notification service is currently unavailable. Please try again later.';

        // Test SocketException
        final socketNotifier = NotificationNotifier(
          api: _ThrowingMockApiClient(SocketException(message)),
        );
        await socketNotifier.fetchNotifications();
        expect(socketNotifier.state.error, equals(expectedError));

        // Test TimeoutException
        final timeoutNotifier = NotificationNotifier(
          api: _ThrowingMockApiClient(TimeoutException(message)),
        );
        await timeoutNotifier.fetchNotifications();
        expect(timeoutNotifier.state.error, equals(expectedError));
      },
    );

    // PBT-3 (property P4):
    // For any exception that is NOT a SocketException or TimeoutException,
    // state.error never equals the service-unavailable string.
    //
    // **Validates: Requirements P4**
    Glados(any.letters).test(
      'PBT-3: generic Exception never yields service-unavailable error',
      (String message) async {
        // Prefix ensures the message does not trigger the auth branch
        // (avoids 'Session expired' or '401' substrings).
        final safeMessage = 'generic_error_$message';

        final notifier = NotificationNotifier(
          api: _ThrowingMockApiClient(Exception(safeMessage)),
        );
        await notifier.fetchNotifications();

        expect(
          notifier.state.error,
          isNot(equals(
            'Notification service is currently unavailable. Please try again later.',
          )),
        );
      },
    );
  });
}