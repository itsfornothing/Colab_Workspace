// Unit tests for AuthNotifier.tryAutoLogin() — Task 4.2
//
// Covers:
//   Any exception thrown by _api.get()  → returns false, clearTokens() called
//   No tokens stored                    → returns false immediately (no network call)
//   200 profile response                → returns true, user populated
//   Non-200 response                    → returns false, clearTokens() called
//
// Validates: Requirements 2.9, 3.6, 3.7

import 'dart:async';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/api_client.dart';
import 'package:mobile_app/core/token_storage.dart';
import 'package:mobile_app/providers/auth_provider.dart';

// ---------------------------------------------------------------------------
// Mock TokenStorage
// ---------------------------------------------------------------------------

class _FakeTokenStorage extends TokenStorage {
  String? _access;
  String? _refresh;
  String? _userId;
  String? _email;
  bool clearTokensCalled = false;

  _FakeTokenStorage({bool hasStoredTokens = true}) : super.internal() {
    if (hasStoredTokens) {
      _access = 'stored-access-token';
      _refresh = 'stored-refresh-token';
    }
  }

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
    clearTokensCalled = true;
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
// Mock ApiClient — GET variants
// ---------------------------------------------------------------------------

class _FixedGetResponseApiClient extends ApiClient {
  final http.Response response;

  _FixedGetResponseApiClient(this.response) : super.internal();

  @override
  Future<http.Response> get(String url) async => response;
}

class _ThrowingGetApiClient extends ApiClient {
  final Object exception;
  bool getCalled = false;

  _ThrowingGetApiClient(this.exception) : super.internal();

  @override
  Future<http.Response> get(String url) {
    getCalled = true;
    return Future.error(exception);
  }
}

class _NeverCalledGetApiClient extends ApiClient {
  bool getCalled = false;

  _NeverCalledGetApiClient() : super.internal();

  @override
  Future<http.Response> get(String url) {
    getCalled = true;
    fail('get() should not have been called when no tokens are stored');
  }
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

AuthNotifier _notifier(ApiClient api, _FakeTokenStorage storage) =>
    AuthNotifier.withDependencies(api: api, storage: storage);

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  // =========================================================================
  // Exception handling — any exception → false + clearTokens()
  // =========================================================================

  group('AuthNotifier.tryAutoLogin() — exception handling', () {
    test('SocketException → returns false and calls clearTokens()', () async {
      final storage = _FakeTokenStorage();
      final api = _ThrowingGetApiClient(
        const SocketException('Connection refused'),
      );
      final notifier = _notifier(api, storage);

      final result = await notifier.tryAutoLogin();

      expect(result, isFalse,
          reason: 'Must return false when a SocketException is thrown');
      expect(storage.clearTokensCalled, isTrue,
          reason: 'clearTokens() must be called when an exception is thrown');
    });

    test('TimeoutException → returns false and calls clearTokens()', () async {
      final storage = _FakeTokenStorage();
      final api = _ThrowingGetApiClient(
        TimeoutException('Request timed out', const Duration(seconds: 30)),
      );
      final notifier = _notifier(api, storage);

      final result = await notifier.tryAutoLogin();

      expect(result, isFalse);
      expect(storage.clearTokensCalled, isTrue);
    });

    test('Exception("Session expired...") → returns false and calls clearTokens()', () async {
      final storage = _FakeTokenStorage();
      final api = _ThrowingGetApiClient(
        Exception('Session expired. Please log in again.'),
      );
      final notifier = _notifier(api, storage);

      final result = await notifier.tryAutoLogin();

      expect(result, isFalse,
          reason: 'Session-expiry exception must return false');
      expect(storage.clearTokensCalled, isTrue,
          reason: 'clearTokens() must be called on session-expiry exception');
    });

    test('Generic Exception → returns false and calls clearTokens()', () async {
      final storage = _FakeTokenStorage();
      final api = _ThrowingGetApiClient(Exception('Unexpected error'));
      final notifier = _notifier(api, storage);

      final result = await notifier.tryAutoLogin();

      expect(result, isFalse);
      expect(storage.clearTokensCalled, isTrue);
    });
  });

  // =========================================================================
  // No tokens stored → returns false immediately, no network call
  // Requirement 3.6
  // =========================================================================

  group('AuthNotifier.tryAutoLogin() — no tokens stored', () {
    test('returns false immediately without making a network request', () async {
      final storage = _FakeTokenStorage(hasStoredTokens: false);
      final api = _NeverCalledGetApiClient();
      final notifier = _notifier(api, storage);

      final result = await notifier.tryAutoLogin();

      expect(result, isFalse,
          reason: 'Must return false when no tokens are stored');
      expect(api.getCalled, isFalse,
          reason: 'No network request should be made when no tokens are stored');
      expect(storage.clearTokensCalled, isFalse,
          reason: 'clearTokens() must NOT be called when no tokens are stored');
    });
  });

  // =========================================================================
  // HTTP response paths
  // =========================================================================

  group('AuthNotifier.tryAutoLogin() — HTTP response paths', () {
    // -----------------------------------------------------------------------
    // 200 response → returns true, user populated
    // Requirement 3.7
    // -----------------------------------------------------------------------
    test('200 profile response → returns true and populates user', () async {
      const responseBody = '''
{
  "id": "user-1",
  "email": "a@b.com",
  "full_name": "Alice"
}
''';
      final storage = _FakeTokenStorage();
      final api = _FixedGetResponseApiClient(http.Response(responseBody, 200));
      final notifier = _notifier(api, storage);

      final result = await notifier.tryAutoLogin();

      expect(result, isTrue,
          reason: 'Must return true when profile endpoint returns 200');
      expect(notifier.state.user, isNotNull,
          reason: 'state.user must be populated after a successful auto-login');
      expect(notifier.state.user!.email, equals('a@b.com'));
      expect(storage.clearTokensCalled, isFalse,
          reason: 'clearTokens() must NOT be called on a successful auto-login');
    });

    // -----------------------------------------------------------------------
    // Non-200 response → returns false, clearTokens() called
    // -----------------------------------------------------------------------
    test('401 response → returns false and calls clearTokens()', () async {
      final storage = _FakeTokenStorage();
      final api = _FixedGetResponseApiClient(
        http.Response('{"detail": "Unauthorized"}', 401),
      );
      final notifier = _notifier(api, storage);

      final result = await notifier.tryAutoLogin();

      expect(result, isFalse,
          reason: 'Must return false when profile endpoint returns non-200');
      expect(storage.clearTokensCalled, isTrue,
          reason: 'clearTokens() must be called when profile endpoint returns non-200');
    });

    test('403 response → returns false and calls clearTokens()', () async {
      final storage = _FakeTokenStorage();
      final api = _FixedGetResponseApiClient(
        http.Response('{"detail": "Forbidden"}', 403),
      );
      final notifier = _notifier(api, storage);

      final result = await notifier.tryAutoLogin();

      expect(result, isFalse);
      expect(storage.clearTokensCalled, isTrue);
    });
  });
}
