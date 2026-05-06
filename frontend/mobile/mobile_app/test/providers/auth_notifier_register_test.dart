// Unit tests for AuthNotifier.register() — Task 3.2
//
// Covers:
//   SocketException          → connectivity string   (Requirement 2.5)
//   TimeoutException         → connectivity string   (Requirement 2.6)
//   Exception('Session expired...') → session-expiry string (Requirement 2.7)
//   Exception('other')       → unexpected-error string (Requirement 2.8)
//   201 response             → no error, isLoading false (Requirement 3.5)
//   400 JSON error response  → server-provided error message (Requirement 3.4)
//
// Validates: Requirements 2.5, 2.6, 2.7, 2.8, 3.4, 3.5

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

  group('AuthNotifier.register() — exception classification', () {
    // -----------------------------------------------------------------------
    // SocketException → connectivity string
    // Requirement 2.5
    // -----------------------------------------------------------------------
    test('SocketException sets connectivity error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(const SocketException('Connection refused')),
      );
      await notifier.register('Alice', 'a@b.com', 'pw');
      expect(notifier.state.error, equals(_kConnectivity),
          reason: 'SocketException must produce the connectivity message');
      expect(notifier.state.isLoading, isFalse,
          reason: 'isLoading must be false after register completes');
    });

    // -----------------------------------------------------------------------
    // TimeoutException → connectivity string
    // Requirement 2.6
    // -----------------------------------------------------------------------
    test('TimeoutException sets connectivity error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(
          TimeoutException('Request timed out', const Duration(seconds: 30)),
        ),
      );
      await notifier.register('Alice', 'a@b.com', 'pw');
      expect(notifier.state.error, equals(_kConnectivity),
          reason: 'TimeoutException must produce the connectivity message');
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // Exception('Session expired...') → session-expiry string
    // Requirement 2.7
    // -----------------------------------------------------------------------
    test('Exception with "Session expired" message sets session-expiry error', () async {
      final notifier = _notifier(
        _ThrowingApiClient(
          Exception('Session expired. Please log in again.'),
        ),
      );
      await notifier.register('Alice', 'a@b.com', 'pw');
      expect(notifier.state.error, equals(_kSessionExpiry),
          reason:
              'Exception containing "Session expired" must produce the session-expiry message');
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // Exception('other') → unexpected-error string
    // Requirement 2.8
    // -----------------------------------------------------------------------
    test('Generic Exception sets unexpected-error message', () async {
      final notifier = _notifier(
        _ThrowingApiClient(Exception('Something went wrong')),
      );
      await notifier.register('Alice', 'a@b.com', 'pw');
      expect(notifier.state.error, equals(_kUnexpected),
          reason: 'A generic Exception must produce the unexpected-error message');
      expect(notifier.state.isLoading, isFalse);
    });
  });

  // =========================================================================
  // HTTP response paths
  // =========================================================================

  group('AuthNotifier.register() — HTTP response paths', () {
    // -----------------------------------------------------------------------
    // 201 response → no error, isLoading false
    // Requirement 3.5
    // -----------------------------------------------------------------------
    test('201 response clears loading state with no error', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response('{}', 201)),
      );
      await notifier.register('Alice', 'a@b.com', 'pw');
      expect(notifier.state.error, isNull,
          reason: 'state.error must be null after a successful 201 registration');
      expect(notifier.state.isLoading, isFalse,
          reason: 'isLoading must be false after register completes');
    });

    test('201 response with empty body clears loading state with no error', () async {
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response('', 201)),
      );
      await notifier.register('Alice', 'a@b.com', 'pw');
      expect(notifier.state.error, isNull);
      expect(notifier.state.isLoading, isFalse);
    });

    // -----------------------------------------------------------------------
    // Non-201 JSON error response → server-provided error message
    // Requirement 3.4
    // -----------------------------------------------------------------------
    test('400 with JSON error body sets server-provided error message', () async {
      const responseBody = '{"error": "Email already in use."}';
      final notifier = _notifier(
        _FixedResponseApiClient(http.Response(responseBody, 400)),
      );
      await notifier.register('Alice', 'a@b.com', 'pw');
      expect(notifier.state.error, equals('Email already in use.'),
          reason: '400 with JSON error field must surface the server message');
      expect(notifier.state.isLoading, isFalse);
    });
  });
}
