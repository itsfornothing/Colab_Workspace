import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../core/constants.dart';
import '../core/token_storage.dart';
import '../models/user.dart';

/// Three-way classification for auth operations.
/// Handles SocketException, TimeoutException, session-expiry, and unexpected errors.
String _classifyAuthException(Object e) {
  if (e is SocketException || e is TimeoutException) {
    return 'Could not connect to server. Check your connection.';
  }
  final msg = e.toString();
  if (msg.contains('Session expired')) {
    return 'Session expired. Please log in again.';
  }
  return 'An unexpected error occurred. Please try again.';
}

class AuthState {
  final User? user;
  final bool isLoading;
  final String? error;

  const AuthState({this.user, this.isLoading = false, this.error});

  AuthState copyWith({User? user, bool? isLoading, String? error}) => AuthState(
        user: user ?? this.user,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );
}

class AuthNotifier extends StateNotifier<AuthState> {
  final ApiClient _api;
  final TokenStorage _storage;

  AuthNotifier()
      : _api = ApiClient(),
        _storage = TokenStorage(),
        super(const AuthState());

  /// Test-only constructor that accepts injected dependencies.
  @visibleForTesting
  AuthNotifier.withDependencies({
    required ApiClient api,
    TokenStorage? storage,
  })  : _api = api,
        _storage = storage ?? TokenStorage(),
        super(const AuthState());

  Future<bool> tryAutoLogin() async {
    if (!await _storage.hasTokens()) return false;
    try {
      final response = await _api.get(AppConstants.profileUrl);
      if (response.statusCode == 200) {
        final user = User.fromJson(jsonDecode(response.body));
        state = state.copyWith(user: user);
        return true;
      }
    } catch (e) {
      // Session-expiry exceptions from _refreshAndRetry are expected here.
      // All other exceptions (SocketException, unexpected) also result in
      // clearing tokens and returning false — the user must re-authenticate.
      await _storage.clearTokens();
      return false;
    }
    await _storage.clearTokens();
    return false;
  }

  Future<void> login(String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final response = await _api.post(
        AppConstants.loginUrl,
        {'email': email, 'password': password},
        auth: false,
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await _storage.setTokens(data['access'], data['refresh']);
        final user = User.fromJson(data['user']);
        await _storage.setUserId(user.id);
        await _storage.setUserEmail(user.email);
        state = state.copyWith(user: user, isLoading: false);
      } else {
        String errorMsg = 'Login failed. Please try again.';
        try {
          final err = jsonDecode(response.body);
          errorMsg = err['error'] ?? err['detail'] ?? err['non_field_errors']?.first ?? errorMsg;
        } catch (_) {
          // Response wasn't JSON (e.g. HTML error page) — use generic message
          if (response.statusCode == 401) errorMsg = 'Invalid email or password.';
          if (response.statusCode == 403) errorMsg = 'Please verify your email before logging in.';
          if (response.statusCode == 429) errorMsg = 'Too many attempts. Try again in 15 minutes.';
          if (response.statusCode >= 500) errorMsg = 'Server error. Please try again later.';
        }
        state = state.copyWith(isLoading: false, error: errorMsg);
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _classifyAuthException(e),
      );
    }
  }

  Future<void> register(String fullName, String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final response = await _api.post(
        AppConstants.registerUrl,
        {'full_name': fullName, 'email': email, 'password': password},
        auth: false,
      );
      if (response.statusCode == 201) {
        state = state.copyWith(isLoading: false);
      } else {
        String errorMsg = 'Registration failed. Please try again.';
        try {
          final err = jsonDecode(response.body);
          errorMsg = err['error'] ?? err['detail'] ?? err['email']?.first ?? errorMsg;
        } catch (_) {
          if (response.statusCode >= 500) errorMsg = 'Server error. Please try again later.';
        }
        state = state.copyWith(isLoading: false, error: errorMsg);
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _classifyAuthException(e),
      );
    }
  }

  Future<void> logout() async {
    try {
      final refreshToken = await _storage.getRefreshToken();
      if (refreshToken != null) {
        await _api.post(AppConstants.logoutUrl, {'refresh': refreshToken});
      }
    } catch (_) {}
    await _storage.clearTokens();
    state = const AuthState();
  }

  void clearError() => state = state.copyWith(error: null);

  /// Directly update the cached user object (e.g. after a profile edit).
  void updateUser(User user) => state = state.copyWith(user: user);
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(),
);
