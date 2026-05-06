// Property-based tests for the auth-error-classification bugfix.
//
// These tests verify that the exception-classification helpers in
// auth_provider.dart and workspace_provider.dart satisfy the six
// correctness properties defined in the design document.
//
// Each property is run with many randomly-generated inputs via the
// Glados PBT library (glados: ^1.1.7).
//
// Validates: Requirements 2.1–2.11

import 'dart:async';
import 'dart:io';
// Hide flutter_test symbols that conflict with glados (which re-exports
// package:test/test.dart and package:matcher).
import 'package:flutter_test/flutter_test.dart'
    hide expect, group, setUp, test, isTrue, isFalse, isNull, isNot, equals,
        anyOf, contains, hasLength, isEmpty, isNotNull;
import 'package:glados/glados.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mobile_app/core/api_client.dart';
import 'package:mobile_app/core/token_storage.dart';
import 'package:mobile_app/providers/auth_provider.dart';
import 'package:mobile_app/providers/workspace_provider.dart';

// ---------------------------------------------------------------------------
// Expected message constants (mirrors the classification helpers)
// ---------------------------------------------------------------------------

const _kConnectivity = 'Could not connect to server. Check your connection.';
const _kSessionExpiry = 'Session expired. Please log in again.';
const _kUnexpected = 'An unexpected error occurred. Please try again.';

// ---------------------------------------------------------------------------
// Mock TokenStorage — in-memory, tracks clearTokensCalled flag
// (reused from auth_notifier_try_auto_login_test.dart)
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
// Mock ApiClient — throws a fixed exception on post()
// (reused from auth_notifier_login_test.dart)
// ---------------------------------------------------------------------------

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
// Mock ApiClient — throws a fixed exception on get()
// (reused from auth_notifier_try_auto_login_test.dart)
// ---------------------------------------------------------------------------

class _ThrowingGetApiClient extends ApiClient {
  final Object exception;

  _ThrowingGetApiClient(this.exception) : super.internal();

  @override
  Future<http.Response> get(String url) => Future.error(exception);
}

// ---------------------------------------------------------------------------
// Helpers: build notifiers with injected dependencies
// ---------------------------------------------------------------------------

AuthNotifier _authNotifier(ApiClient api, {_FakeTokenStorage? storage}) =>
    AuthNotifier.withDependencies(
      api: api,
      storage: storage ?? _FakeTokenStorage(),
    );

WorkspaceNotifier _workspaceNotifier(ApiClient api) =>
    WorkspaceNotifier.withDependencies(api: api);

// ---------------------------------------------------------------------------
// String generators for use with Glados.
//
// Glados 1.1.7 does not register String as a default type, so we use
// any.letters (lowercase a-z) as a safe, shrinkable string generator.
//
// _nonSessionExpiredString: letters-only strings can never contain the
// substring 'Session expired' (which requires uppercase S and spaces),
// so they are safe inputs for Properties 3 and 4.
// ---------------------------------------------------------------------------

/// Generates arbitrary lowercase-letter strings (a-z).
/// These strings can never contain 'Session expired', making them safe
/// inputs for the unexpected-error classification properties.
final _safeString = any.letters;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  // =========================================================================
  // Property 1: For any SocketException or TimeoutException, login() sets
  // state.error to the connectivity string.
  //
  // Feature: auth-error-classification, Property 1
  // Validates: Requirements 2.1, 2.2
  // =========================================================================

  group('Property 1 — login() connectivity classification', () {
    Glados(any.letters).test(
      'SocketException with any message → connectivity string',
      (socketMsg) async {
        final notifier = _authNotifier(
          _ThrowingApiClient(SocketException(socketMsg)),
        );
        await notifier.login('a@b.com', 'pw');
        expect(notifier.state.error, equals(_kConnectivity));
        expect(notifier.state.isLoading, isFalse);
      },
    );

    Glados(any.letters).test(
      'TimeoutException with any message → connectivity string',
      (timeoutMsg) async {
        final notifier = _authNotifier(
          _ThrowingApiClient(TimeoutException(timeoutMsg)),
        );
        await notifier.login('a@b.com', 'pw');
        expect(notifier.state.error, equals(_kConnectivity));
        expect(notifier.state.isLoading, isFalse);
      },
    );
  });

  // =========================================================================
  // Property 2: For any Exception whose message contains 'Session expired',
  // login() sets state.error to the session-expiry string.
  //
  // Feature: auth-error-classification, Property 2
  // Validates: Requirement 2.3
  // =========================================================================

  group('Property 2 — login() session-expiry classification', () {
    Glados(any.letters).test(
      'Exception("Session expired" + any suffix) → session-expiry string',
      (suffix) async {
        final msg = 'Session expired$suffix';
        final notifier = _authNotifier(
          _ThrowingApiClient(Exception(msg)),
        );
        await notifier.login('a@b.com', 'pw');
        expect(notifier.state.error, equals(_kSessionExpiry));
        expect(notifier.state.isLoading, isFalse);
      },
    );
  });

  // =========================================================================
  // Property 3: For any exception that is neither connectivity nor
  // session-expiry, login() sets state.error to the unexpected-error string.
  //
  // Feature: auth-error-classification, Property 3
  // Validates: Requirement 2.4
  //
  // Note: any.letters generates lowercase a-z strings, which can never
  // contain 'Session expired' (requires uppercase S and spaces), so no
  // filtering is needed.
  // =========================================================================

  group('Property 3 — login() unexpected-error classification', () {
    Glados(_safeString).test(
      'Exception with message not containing "Session expired" → unexpected string',
      (msg) async {
        final notifier = _authNotifier(
          _ThrowingApiClient(Exception(msg)),
        );
        await notifier.login('a@b.com', 'pw');
        expect(notifier.state.error, equals(_kUnexpected));
        expect(notifier.state.isLoading, isFalse);
      },
    );
  });

  // =========================================================================
  // Property 4: For any exception, register() produces the same error string
  // as login() would for the same exception.
  //
  // Feature: auth-error-classification, Property 4
  // Validates: Requirements 2.5, 2.6, 2.7, 2.8
  // =========================================================================

  group('Property 4 — register() mirrors login() classification', () {
    Glados(any.letters).test(
      'SocketException: register() error == login() error',
      (socketMsg) async {
        final exception = SocketException(socketMsg);

        final loginNotifier = _authNotifier(_ThrowingApiClient(exception));
        await loginNotifier.login('a@b.com', 'pw');

        final registerNotifier = _authNotifier(_ThrowingApiClient(exception));
        await registerNotifier.register('Alice', 'a@b.com', 'pw');

        expect(registerNotifier.state.error, equals(loginNotifier.state.error));
      },
    );

    Glados(any.letters).test(
      'TimeoutException: register() error == login() error',
      (timeoutMsg) async {
        final exception = TimeoutException(timeoutMsg);

        final loginNotifier = _authNotifier(_ThrowingApiClient(exception));
        await loginNotifier.login('a@b.com', 'pw');

        final registerNotifier = _authNotifier(_ThrowingApiClient(exception));
        await registerNotifier.register('Alice', 'a@b.com', 'pw');

        expect(registerNotifier.state.error, equals(loginNotifier.state.error));
      },
    );

    Glados(any.letters).test(
      'Exception("Session expired" + suffix): register() error == login() error',
      (suffix) async {
        final exception = Exception('Session expired$suffix');

        final loginNotifier = _authNotifier(_ThrowingApiClient(exception));
        await loginNotifier.login('a@b.com', 'pw');

        final registerNotifier = _authNotifier(_ThrowingApiClient(exception));
        await registerNotifier.register('Alice', 'a@b.com', 'pw');

        expect(registerNotifier.state.error, equals(loginNotifier.state.error));
      },
    );

    Glados(_safeString).test(
      'Generic Exception (no "Session expired"): register() error == login() error',
      (msg) async {
        final exception = Exception(msg);

        final loginNotifier = _authNotifier(_ThrowingApiClient(exception));
        await loginNotifier.login('a@b.com', 'pw');

        final registerNotifier = _authNotifier(_ThrowingApiClient(exception));
        await registerNotifier.register('Alice', 'a@b.com', 'pw');

        expect(registerNotifier.state.error, equals(loginNotifier.state.error));
      },
    );
  });

  // =========================================================================
  // Property 5: For any exception, tryAutoLogin() returns false and calls
  // clearTokens().
  //
  // Feature: auth-error-classification, Property 5
  // Validates: Requirement 2.9
  // =========================================================================

  group('Property 5 — tryAutoLogin() always returns false and clears tokens', () {
    Glados(any.letters).test(
      'SocketException with any message → false + clearTokens()',
      (socketMsg) async {
        final storage = _FakeTokenStorage();
        final notifier = _authNotifier(
          _ThrowingGetApiClient(SocketException(socketMsg)),
          storage: storage,
        );
        final result = await notifier.tryAutoLogin();
        expect(result, isFalse);
        expect(storage.clearTokensCalled, isTrue);
      },
    );

    Glados(any.letters).test(
      'TimeoutException with any message → false + clearTokens()',
      (timeoutMsg) async {
        final storage = _FakeTokenStorage();
        final notifier = _authNotifier(
          _ThrowingGetApiClient(TimeoutException(timeoutMsg)),
          storage: storage,
        );
        final result = await notifier.tryAutoLogin();
        expect(result, isFalse);
        expect(storage.clearTokensCalled, isTrue);
      },
    );

    Glados(any.letters).test(
      'Generic Exception with any message → false + clearTokens()',
      (msg) async {
        final storage = _FakeTokenStorage();
        final notifier = _authNotifier(
          _ThrowingGetApiClient(Exception(msg)),
          storage: storage,
        );
        final result = await notifier.tryAutoLogin();
        expect(result, isFalse);
        expect(storage.clearTokensCalled, isTrue);
      },
    );
  });

  // =========================================================================
  // Property 6: For any exception, loadWorkspaces() sets state.error to one
  // of the two allowed strings and never to e.toString().
  //
  // Feature: auth-error-classification, Property 6
  // Validates: Requirements 2.10, 2.11
  // =========================================================================

  group('Property 6 — loadWorkspaces() never exposes raw exception strings', () {
    Glados(any.letters).test(
      'Exception with any message → state.error is one of the two allowed strings',
      (msg) async {
        final exception = Exception(msg);
        final notifier = _workspaceNotifier(
          _ThrowingGetApiClient(exception),
        );
        await notifier.loadWorkspaces();
        expect(
          notifier.state.error,
          anyOf(equals(_kConnectivity), equals(_kUnexpected)),
          reason: 'state.error must be one of the two allowed classification strings',
        );
        expect(
          notifier.state.error,
          isNot(equals(exception.toString())),
          reason: 'state.error must never be the raw e.toString() output',
        );
        expect(notifier.state.isLoading, isFalse);
      },
    );
  });
}
