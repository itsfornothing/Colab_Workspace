import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/api_client.dart';
import '../core/constants.dart';
import '../models/workspace.dart';

/// Two-way classification for non-auth operations (no session-expiry branch).
/// Returns the connectivity string for [SocketException]/[TimeoutException]
/// and the unexpected-error string for all other exceptions.
String _classifyConnectivityException(Object e) {
  if (e is SocketException || e is TimeoutException) {
    return 'Could not connect to server. Check your connection.';
  }
  return 'An unexpected error occurred. Please try again.';
}

class WorkspaceState {
  final List<Workspace> workspaces;
  final String? currentWorkspaceId;
  final List<Channel> channels;
  final bool isLoading;
  final String? error;

  const WorkspaceState({
    this.workspaces = const [],
    this.currentWorkspaceId,
    this.channels = const [],
    this.isLoading = false,
    this.error,
  });

  Workspace? get currentWorkspace =>
      workspaces.where((w) => w.id == currentWorkspaceId).firstOrNull;

  WorkspaceState copyWith({
    List<Workspace>? workspaces,
    String? currentWorkspaceId,
    List<Channel>? channels,
    bool? isLoading,
    String? error,
  }) =>
      WorkspaceState(
        workspaces: workspaces ?? this.workspaces,
        currentWorkspaceId: currentWorkspaceId ?? this.currentWorkspaceId,
        channels: channels ?? this.channels,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );
}

class WorkspaceNotifier extends StateNotifier<WorkspaceState> {
  final ApiClient _api;

  WorkspaceNotifier()
      : _api = ApiClient(),
        super(const WorkspaceState());

  /// Test-only constructor that accepts an injected [ApiClient].
  @visibleForTesting
  WorkspaceNotifier.withDependencies({required ApiClient api})
      : _api = api,
        super(const WorkspaceState());

  Future<void> loadWorkspaces() async {
    state = state.copyWith(isLoading: true);
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedId = prefs.getString(AppConstants.workspaceIdKey);

      final response = await _api.get(AppConstants.workspacesListUrl);
      if (response.statusCode == 200) {
        final list = (jsonDecode(response.body) as List)
            .map((w) => Workspace.fromJson(w))
            .toList();
        final currentId = savedId ?? (list.isNotEmpty ? list.first.id : null);
        state = state.copyWith(
          workspaces: list,
          currentWorkspaceId: currentId,
          isLoading: false,
        );
        if (currentId != null) await loadChannels(currentId);
      } else {
        state = state.copyWith(isLoading: false, error: 'Failed to load workspaces');
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _classifyConnectivityException(e),
      );
    }
  }

  Future<void> switchWorkspace(String workspaceId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConstants.workspaceIdKey, workspaceId);
    state = state.copyWith(currentWorkspaceId: workspaceId);
    await loadChannels(workspaceId);
  }

  Future<void> loadChannels(String workspaceId) async {
    try {
      final response = await _api.get(AppConstants.workspaceChannelsUrl(workspaceId));
      if (response.statusCode == 200) {
        final list = (jsonDecode(response.body) as List)
            .map((c) => Channel.fromJson(c))
            .toList();
        state = state.copyWith(channels: list);
      }
    } catch (_) {}
  }
}

final workspaceProvider = StateNotifierProvider<WorkspaceNotifier, WorkspaceState>(
  (ref) => WorkspaceNotifier(),
);
