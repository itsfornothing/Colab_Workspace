// Unit tests for WorkspaceNotifier.loadWorkspaces() — Task 6.2
//
// Covers:
//   SocketException          → connectivity string   (Requirement 2.10)
//   TimeoutException         → connectivity string   (Requirement 2.10)
//   Exception('anything')    → unexpected-error string, never e.toString() (Requirement 2.11)
//   200 response             → workspaces populated, no error (Requirement 3.9)
//   non-200 response         → 'Failed to load workspaces' (Requirement 3.10)
//
// Validates: Requirements 2.10, 2.11, 3.9, 3.10

import 'dart:async';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mobile_app/core/api_client.dart';
import 'package:mobile_app/providers/workspace_provider.dart';

// ---------------------------------------------------------------------------
// Expected message constants (mirrors _classifyConnectivityException)
// ---------------------------------------------------------------------------

const _kConnectivity = 'Could not connect to server. Check your connection.';
const _kUnexpected = 'An unexpected error occurred. Please try again.';
const _kFailedToLoad = 'Failed to load workspaces';

// ---------------------------------------------------------------------------
// Mock ApiClient — get() returns a fixed response or throws a fixed exception
// ---------------------------------------------------------------------------

/// Returns a fixed [http.Response] for every get() call.
class _FixedResponseApiClient extends ApiClient {
  final http.Response response;

  _FixedResponseApiClient(this.response) : super.internal();

  @override
  Future<http.Response> get(String url) async => response;
}

/// Throws a fixed exception for every get() call.
class _ThrowingApiClient extends ApiClient {
  final Object exception;

  _ThrowingApiClient(this.exception) : super.internal();

  @override
  Future<http.Response> get(String url) => Future.error(exception);
}

// ---------------------------------------------------------------------------
// Helper: build a WorkspaceNotifier backed by the given ApiClient
// ---------------------------------------------------------------------------

WorkspaceNotifier _notifier(ApiClient api) =>
    WorkspaceNotifier.withDependencies(api: api);

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  // SharedPreferences must be initialised before each test so that
  // loadWorkspaces() can call SharedPreferences.getInstance() without
  // hitting the platform channel.
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  // =========================================================================
  // Exception classification — catch (e) block
  // =========================================================================

  group('WorkspaceNotifier.loadWorkspaces() — exception classification', () {
    // -----------------------------------------------------------------------
    // SocketException → connectivity string
    // Requirement 2.10
    // -----------------------------------------------------------------------
    test('SocketException sets connectivity error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(const SocketException('Connection refused')),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kConnectivity),
          reason: 'SocketException must produce the connectivity message');
      expect(notifier.state.isLoading, isFalse,
          reason: 'isLoading must be false after loadWorkspaces completes');
    });

    test('SocketException (host lookup failure) sets connectivity error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(
          const SocketException('Failed host lookup: workspace.example.com'),
        ),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kConnectivity));
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // TimeoutException → connectivity string
    // Requirement 2.10
    // -----------------------------------------------------------------------
    test('TimeoutException sets connectivity error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(
          TimeoutException('Request timed out', const Duration(seconds: 30)),
        ),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kConnectivity),
          reason: 'TimeoutException must produce the connectivity message');
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // Exception('anything') → unexpected-error string, never e.toString()
    // Requirement 2.11
    // -----------------------------------------------------------------------
    test('Generic Exception sets unexpected-error message (not e.toString())', () async {
      final exception = Exception('Something went wrong internally');
      final notifier = _notifier(_ThrowingApiClient(exception));
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kUnexpected),
          reason: 'A generic Exception must produce the unexpected-error message');
      expect(notifier.state.error, isNot(equals(exception.toString())),
          reason: 'state.error must never be e.toString()');
      expect(notifier.state.isLoading, isFalse);
    });

    test('FormatException sets unexpected-error message (not e.toString())', () async {
      final exception = const FormatException('bad json response');
      final notifier = _notifier(_ThrowingApiClient(exception));
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kUnexpected),
          reason: 'FormatException must produce the unexpected-error message');
      expect(notifier.state.error, isNot(equals(exception.toString())));
    });

    test('Exception with arbitrary message is never exposed raw', () async {
      final exception = Exception('Internal server details: DB connection pool exhausted');
      final notifier = _notifier(_ThrowingApiClient(exception));
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kUnexpected),
          reason: 'Raw exception details must never reach the UI');
      expect(notifier.state.error, isNot(contains('DB connection pool exhausted')),
          reason: 'Internal exception message must not be exposed');
    });

    test('StateError sets unexpected-error message (not e.toString())', () async {
      final exception = StateError('bad state');
      final notifier = _notifier(_ThrowingApiClient(exception));
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kUnexpected));
      expect(notifier.state.error, isNot(equals(exception.toString())));
    });
  });

  // =========================================================================
  // HTTP response paths
  // =========================================================================

  group('WorkspaceNotifier.loadWorkspaces() — HTTP response paths', () {
    // -----------------------------------------------------------------------
    // 200 response → workspaces populated, no error
    // Requirement 3.9
    // -----------------------------------------------------------------------
    test('200 response populates workspaces and clears error', () async {
      const responseBody = '''
[
  {"id": "ws-1", "name": "Engineering", "member_count": 5},
  {"id": "ws-2", "name": "Design", "member_count": 3}
]
''';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 200)),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, isNull,
          reason: 'state.error must be null after a successful 200 response');
      expect(notifier.state.isLoading, isFalse,
          reason: 'isLoading must be false after loadWorkspaces completes');
      expect(notifier.state.workspaces, hasLength(2),
          reason: 'Both workspaces from the response must be stored in state');
      expect(notifier.state.workspaces.first.id, equals('ws-1'));
      expect(notifier.state.workspaces.first.name, equals('Engineering'));
      expect(notifier.state.workspaces[1].id, equals('ws-2'));
    });

    test('200 response with single workspace sets currentWorkspaceId', () async {
      const responseBody = '[{"id": "ws-1", "name": "My Workspace", "member_count": 1}]';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 200)),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, isNull);
      expect(notifier.state.workspaces, hasLength(1));
      // currentWorkspaceId should be set to the first workspace when no saved ID
      expect(notifier.state.currentWorkspaceId, equals('ws-1'));
    });

    test('200 response with empty list results in no error and empty workspaces', () async {
      const responseBody = '[]';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 200)),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, isNull);
      expect(notifier.state.workspaces, isEmpty);
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // non-200 response → 'Failed to load workspaces' (existing behavior)
    // Requirement 3.10
    // -----------------------------------------------------------------------
    test('non-200 response sets "Failed to load workspaces" error', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response('{"detail": "Not found."}', 404)),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kFailedToLoad),
          reason: 'non-200 HTTP response must produce the "Failed to load workspaces" message');
      expect(notifier.state.isLoading, isFalse);
    });

    test('500 response sets "Failed to load workspaces" error', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(
          http.Response('<html>Internal Server Error</html>', 500),
        ),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kFailedToLoad),
          reason: '500 response must produce the "Failed to load workspaces" message');
      expect(notifier.state.isLoading, isFalse);
    });

    test('401 response sets "Failed to load workspaces" error', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response('{"detail": "Unauthorized"}', 401)),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.error, equals(_kFailedToLoad));
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // isLoading lifecycle
    // -----------------------------------------------------------------------
    test('isLoading is false after a successful load', () async {
      const responseBody = '[{"id": "ws-1", "name": "Test", "member_count": 1}]';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 200)),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.isLoading, isFalse);
    });

    test('isLoading is false after a failed load (exception)', () async {
      final notifier = _notifier(
        _ThrowingApiClient(const SocketException('no network')),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.isLoading, isFalse);
    });

    test('isLoading is false after a non-200 response', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response('{}', 503)),
      );
      await notifier.loadWorkspaces();
      expect(notifier.state.isLoading, isFalse);
    });
  });
}
