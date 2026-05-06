// Unit tests for AuthNotifier.login() — Task 2.2
//
// Covers:
//   SocketException          → connectivity string
//   TimeoutException         → connectivity string
//   Exception('Session expired...') → session-expiry string
//   Exception('other')       → unexpected-error string
//   200 response             → no error, user populated
//   401 JSON response        → server-provided error message
//   401 non-JSON response    → 'Invalid email or password.'
//
// Validates: Requirements 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3

import 'dart:async';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/api_client.dart';
import 'package:mobile_app/core/token_storage.dart';
import 'package:mobile_app/providers/auth_provider.dart';

// ---------------------------------------------------------------------------
// Expected message constants (mirrors _classifyAuthException in auth_provider)
// ---------------------------------------------------------------------------

const _kConnectivity = 'Could not connect to server. Check your connection.';
const _kSessionExpiry = 'Session expired. Please log in again.';
const _kUnexpected = 'An unexpected error occurred. Please try again.';
const _kInvalidCredentials = 'Invalid email or password.';

// ---------------------------------------------------------------------------
// Mock TokenStorage — in-memory, no FlutterSecureStorage dependency
// ---------------------------------------------------------------------------

class _FakeTokenStorage extends TokenStorage {
  String? _access;
  String? _refresh;
  String? _userId;
  String? _email;

  _FakeTokenStorage() : super.internal();

  @override
  Future<void> setTokens(String accessToken, String refreshToken) async {
    _access = accessToken;
    _refresh = refreshToken;
  }

  @override
  Future<String?> getAccessToken() async => _access;

  @override
  Future<String?> getRefreshToken() async => _refresh;

  @override
  Future<bool> hasTokens() async => _access != null;

  @override
  Future<void> clearTokens() async {
    _access = null;
    _refresh = null;
    _userId = null;
    _email = null;
  }

  @override
  Future<void> setUserId(String userId) async => _userId = userId;

  @override
  Future<String?> getUserId() async => _userId;

  @override
  Future<void> setUserEmail(String email) async => _email = email;

  @override
  Future<String?> getUserEmail() async => _email;
}

// ---------------------------------------------------------------------------
// Mock ApiClient — post() returns a fixed response or throws a fixed exception
// ---------------------------------------------------------------------------

/// Returns a fixed [http.Response] for every post() call.
class _FixedResponseApiClient extends ApiClient {
  final http.Response response;

  _FixedResponseApiClient(this.response) : super.internal();

  @override
  Future<http.Response> post(
    String url,
    Map<String, dynamic> body, {
    bool auth = true,
  }) async =>
      response;
}

/// Throws a fixed exception for every post() call.
class _ThrowingApiClient extends ApiClient {
  final Object exception;

  _ThrowingApiClient(this.exception) : super.internal();

  @override
  Future<http.Response> post(
    String url,
    Map<String, dynamic> body, {
    bool auth = true,
  }) =>
      Future.error(exception);
}

// ---------------------------------------------------------------------------
// Helper: build an AuthNotifier backed by the given ApiClient + fake storage
// ---------------------------------------------------------------------------

AuthNotifier _notifier(ApiClient api) =>
    AuthNotifier.withDependencies(api: api, storage: _FakeTokenStorage());

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  // =========================================================================
  // Exception classification — catch (e) block
  // =========================================================================

  group('AuthNotifier.login() — exception classification', () {
    // -----------------------------------------------------------------------
    // SocketException → connectivity string
    // Requirement 2.1
    // -----------------------------------------------------------------------
    test('SocketException sets connectivity error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(const SocketException('Connection refused')),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, equals(_kConnectivity),
          reason: 'SocketException must produce the connectivity message');
      expect(notifier.state.isLoading, isFalse,
          reason: 'isLoading must be false after login completes');
    });

    test('SocketException (host lookup failure) sets connectivity error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(
          const SocketException('Failed host lookup: auth.example.com'),
        ),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, equals(_kConnectivity));
    });

    // -----------------------------------------------------------------------
    // TimeoutException → connectivity string
    // Requirement 2.2
    // -----------------------------------------------------------------------
    test('TimeoutException sets connectivity error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(
          TimeoutException('Request timed out', const Duration(seconds: 30)),
        ),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, equals(_kConnectivity),
          reason: 'TimeoutException must produce the connectivity message');
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // Exception('Session expired...') → session-expiry string
    // Requirement 2.3
    // -----------------------------------------------------------------------
    test('Exception with "Session expired" message sets session-expiry error', () async {
      final notifier = _notifier(
        _ThrowingApiClient(
          Exception('Session expired. Please log in again.'),
        ),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, equals(_kSessionExpiry),
          reason: 'Exception containing "Session expired" must produce the session-expiry message');
      expect(notifier.state.isLoading, isFalse);
    });

    test('Exception with "Session expired" substring sets session-expiry error', () async {
      final notifier = _notifier(
        _ThrowingApiClient(Exception('Session expired - token invalid')),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, equals(_kSessionExpiry),
          reason: 'Substring match on "Session expired" must produce the session-expiry message');
    });

    // -----------------------------------------------------------------------
    // Exception('other') → unexpected-error string
    // Requirement 2.4
    // -----------------------------------------------------------------------
    test('Generic Exception sets unexpected-error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(Exception('Something went wrong')),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, equals(_kUnexpected),
          reason: 'A generic Exception must produce the unexpected-error message');
      expect(notifier.state.isLoading, isFalse);
    });

    test('FormatException sets unexpected-error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(const FormatException('bad json')),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, equals(_kUnexpected),
          reason: 'FormatException must produce the unexpected-error message');
    });

    test('Exception with empty message sets unexpected-error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(Exception('')),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, equals(_kUnexpected));
    });
  });

  // =========================================================================
  // HTTP response paths
  // =========================================================================

  group('AuthNotifier.login() — HTTP response paths', () {
    // -----------------------------------------------------------------------
    // 200 response → no error, user populated
    // Requirement 3.3
    // -----------------------------------------------------------------------
    test('200 response clears error and populates user', () async {
      const responseBody = '''
{
  "access": "access-token-abc",
  "refresh": "refresh-token-xyz",
  "user": {
    "id": "user-1",
    "email": "a@b.com",
    "full_name": "Alice"
  }
}
''';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 200)),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error, isNull,
          reason: 'state.error must be null after a successful 200 login');
      expect(notifier.state.isLoading, isFalse,
          reason: 'isLoading must be false after login completes');
      expect(notifier.state.user, isNotNull,
          reason: 'state.user must be populated after a successful login');
      expect(notifier.state.user!.email, equals('a@b.com'));
    });

    // -----------------------------------------------------------------------
    // 401 with JSON body → server-provided error message
    // Requirement 3.1
    // -----------------------------------------------------------------------
    test('401 with JSON error body sets server-provided error message', () async {
      const responseBody = '{"error": "Invalid email or password."}';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 401)),
      );
      await notifier.login('a@b.com', 'wrong-pw');
      expect(notifier.state.error, equals('Invalid email or password.'),
          reason: '401 with JSON error field must surface the server message');
      expect(notifier.state.isLoading, isFalse);
      expect(notifier.state.user, isNull,
          reason: 'state.user must remain null after a failed login');
    });

    test('401 with JSON "detail" field sets server-provided error message', () async {
      const responseBody = '{"detail": "No active account found with the given credentials."}';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 401)),
      );
      await notifier.login('a@b.com', 'wrong-pw');
      expect(notifier.state.error,
          equals('No active account found with the given credentials.'));
    });

    // -----------------------------------------------------------------------
    // 401 with non-JSON body → 'Invalid email or password.'
    // Requirement 3.2
    // -----------------------------------------------------------------------
    test('401 with non-JSON body sets invalid-credentials message', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(
          http.Response('<html>Unauthorized</html>', 401),
        ),
      );
      await notifier.login('a@b.com', 'wrong-pw');
      expect(notifier.state.error, equals(_kInvalidCredentials),
          reason: '401 with non-JSON body must produce the invalid-credentials message');
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // Additional HTTP status codes (regression prevention)
    // -----------------------------------------------------------------------
    test('403 with non-JSON body sets email-verification message', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(
          http.Response('<html>Forbidden</html>', 403),
        ),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error,
          equals('Please verify your email before logging in.'));
    });

    test('429 with non-JSON body sets rate-limit message', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(
          http.Response('<html>Too Many Requests</html>', 429),
        ),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error,
          equals('Too many attempts. Try again in 15 minutes.'));
    });

    test('500 with non-JSON body sets server-error message', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(
          http.Response('<html>Internal Server Error</html>', 500),
        ),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.error,
          equals('Server error. Please try again later.'));
    });

    // -----------------------------------------------------------------------
    // isLoading lifecycle
    // -----------------------------------------------------------------------
    test('isLoading is false after a successful login', () async {
      const responseBody = '''
{
  "access": "tok",
  "refresh": "ref",
  "user": {"id": "1", "email": "a@b.com", "full_name": "A"}
}
''';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 200)),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.isLoading, isFalse);
    });

    test('isLoading is false after a failed login (exception)', () async {
      final notifier = _notifier(
        _ThrowingApiClient(const SocketException('no network')),
      );
      await notifier.login('a@b.com', 'pw');
      expect(notifier.state.isLoading, isFalse);
    });
  });
}
