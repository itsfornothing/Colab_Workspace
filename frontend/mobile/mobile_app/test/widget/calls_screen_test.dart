
// Widget tests for CallsScreen
//
// Tests:
//   1. Workspace guard: null workspaceId → no spinner, explanatory message,
//      navigation button present.
//   2. Load rooms failure: _loadRooms error → error message and retry button.
//   3. Start call with missing room id: _startCall returns body without 'id'
//      → SnackBar shown, no navigation to VideoCallScreen.
//
// Validates: Requirements 10.1, 10.2, 11.1, 11.5
//
// HTTP mocking strategy:
// ApiClient uses the top-level http.get() / http.post() functions from the
// `http` package. These functions call `Client()` which checks
// `Zone.current[#_clientToken]` (the zone-local client set by
// `http.runWithClient`). We wrap each test body in `http.runWithClient` with
// a `_MockHttpClient` that returns controlled responses, so no real network
// calls are made.

import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/providers/workspace_provider.dart';
import 'package:mobile_app/screens/calls/calls_screen.dart';
import 'package:mobile_app/screens/calls/video_call_screen.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Mock HTTP clients
// ─────────────────────────────────────────────────────────────────────────────

/// Returns a fixed [statusCode] and [body] for every request.
class _FixedMockClient extends http.BaseClient {
  final int statusCode;
  final String body;

  _FixedMockClient({required this.statusCode, required this.body});

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return http.StreamedResponse(
      Stream.value(utf8.encode(body)),
      statusCode,
      headers: {'content-type': 'application/json'},
    );
  }
}

/// Throws a [http.ClientException] for every request, simulating a network
/// failure (connection refused, DNS failure, etc.).
class _NetworkErrorMockClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    throw http.ClientException('Simulated network error', request.url);
  }
}

/// Returns different responses for GET vs POST requests.
/// Used by _startCall tests where _loadRooms (GET) must succeed so the main
/// content is rendered, and _startCall (POST) returns a controlled response.
class _DispatchMockClient extends http.BaseClient {
  final int getStatusCode;
  final String getBody;
  final int postStatusCode;
  final String postBody;

  _DispatchMockClient({
    required this.getStatusCode,
    required this.getBody,
    required this.postStatusCode,
    required this.postBody,
  });

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final isPost = request.method.toUpperCase() == 'POST';
    final code = isPost ? postStatusCode : getStatusCode;
    final responseBody = isPost ? postBody : getBody;
    return http.StreamedResponse(
      Stream.value(utf8.encode(responseBody)),
      code,
      headers: {'content-type': 'application/json'},
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Fake WorkspaceNotifiers
// ─────────────────────────────────────────────────────────────────────────────

/// Provides a WorkspaceState with currentWorkspaceId == null.
class _NullWorkspaceNotifier extends WorkspaceNotifier {
  _NullWorkspaceNotifier() : super() {
    state = const WorkspaceState(
      workspaces: [],
      currentWorkspaceId: null,
      channels: [],
      isLoading: false,
    );
  }

  @override
  Future<void> loadWorkspaces() async {}

  @override
  Future<void> switchWorkspace(String workspaceId) async {}

  @override
  Future<void> loadChannels(String workspaceId) async {}
}

/// Provides a WorkspaceState with a valid currentWorkspaceId.
class _ValidWorkspaceNotifier extends WorkspaceNotifier {
  _ValidWorkspaceNotifier() : super() {
    state = const WorkspaceState(
      workspaces: [],
      currentWorkspaceId: 'ws-test-1',
      channels: [],
      isLoading: false,
    );
  }

  @override
  Future<void> loadWorkspaces() async {}

  @override
  Future<void> switchWorkspace(String workspaceId) async {}

  @override
  Future<void> loadChannels(String workspaceId) async {}
}

// ─────────────────────────────────────────────────────────────────────────────
// Widget builder helpers
// ─────────────────────────────────────────────────────────────────────────────

Widget _buildCallsScreenNoWorkspace({void Function(int)? onSwitchTab}) {
  return ProviderScope(
    overrides: [
      workspaceProvider.overrideWith((_) => _NullWorkspaceNotifier()),
    ],
    child: MaterialApp(
      home: CallsScreen(onSwitchTab: onSwitchTab ?? (_) {}),
    ),
  );
}

Widget _buildCallsScreenWithWorkspace({void Function(int)? onSwitchTab}) {
  return ProviderScope(
    overrides: [
      workspaceProvider.overrideWith((_) => _ValidWorkspaceNotifier()),
    ],
    child: MaterialApp(
      home: CallsScreen(onSwitchTab: onSwitchTab ?? (_) {}),
    ),
  );
}

/// Runs [body] inside an `http.runWithClient` zone so that all HTTP calls
/// made by ApiClient are intercepted by [client].
Future<void> _withMockHttp(
  http.Client client,
  Future<void> Function() body,
) async {
  await http.runWithClient(body, () => client);
}

/// Sets up a mock for the `flutter_secure_storage` platform channel so that
/// `TokenStorage.getAccessToken()` returns null immediately instead of
/// hanging on a missing platform channel in the test environment.
///
/// Must be called in `setUp` for any test group that triggers HTTP calls
/// through `ApiClient` (which calls `_storage.getAccessToken()` before
/// every request).
void _setupSecureStorageMock() {
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
    const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
    (MethodCall call) async {
      // Return null for all reads (getAccessToken returns null → no auth header)
      // and silently succeed for all writes/deletes.
      if (call.method == 'read') return null;
      return null;
    },
  );
}

/// Tears down the `flutter_secure_storage` mock after a test group.
void _teardownSecureStorageMock() {
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
    const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
    null,
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  // ---------------------------------------------------------------------------
  // Group 1: Workspace guard (null workspaceId)
  //
  // When workspaceId is null, CallsScreen must:
  //   - NOT show a CircularProgressIndicator (Requirement 10.2)
  //   - Show an explanatory message (Requirement 10.1)
  //   - Show a navigation button (Requirement 10.3)
  //
  // These tests do not make HTTP calls (the workspace guard fires before any
  // network request), so no mock client is needed.
  // ---------------------------------------------------------------------------

  group('CallsScreen — workspace guard (null workspaceId)', () {
    testWidgets(
      'does NOT show CircularProgressIndicator when workspaceId is null (Req 10.2)',
      (WidgetTester tester) async {
        await tester.pumpWidget(_buildCallsScreenNoWorkspace());
        await tester.pump();

        expect(
          find.byType(CircularProgressIndicator),
          findsNothing,
          reason:
              'CallsScreen must NOT show a loading spinner when no workspace '
              'is selected (Requirement 10.2)',
        );
      },
    );

    testWidgets(
      'shows explanatory message when workspaceId is null (Req 10.1)',
      (WidgetTester tester) async {
        await tester.pumpWidget(_buildCallsScreenNoWorkspace());
        await tester.pump();

        expect(
          find.text('Select a workspace to start or join calls'),
          findsOneWidget,
          reason:
              'CallsScreen must display an explanatory message when no workspace '
              'is selected (Requirement 10.1)',
        );
      },
    );

    testWidgets(
      'shows a "Go to Home" navigation button when workspaceId is null (Req 10.3)',
      (WidgetTester tester) async {
        await tester.pumpWidget(_buildCallsScreenNoWorkspace());
        await tester.pump();

        // _NoWorkspaceView renders ElevatedButton.icon with label "Go to Home".
        // ElevatedButton.icon creates a private _ElevatedButtonWithIcon widget,
        // so we find it by the label text rather than by widget type.
        expect(
          find.text('Go to Home'),
          findsOneWidget,
          reason:
              'CallsScreen must show a "Go to Home" navigation button when no '
              'workspace is selected (Requirement 10.3)',
        );
      },
    );

    testWidgets(
      '"Go to Home" button calls onSwitchTab(0) (Req 10.3)',
      (WidgetTester tester) async {
        final List<int> calls = [];

        await tester.pumpWidget(
          _buildCallsScreenNoWorkspace(onSwitchTab: (i) => calls.add(i)),
        );
        await tester.pump();

        await tester.tap(find.text('Go to Home'));
        await tester.pump();

        expect(
          calls,
          contains(0),
          reason:
              '"Go to Home" must call onSwitchTab(0) to navigate to the Home '
              'tab (Requirement 10.3)',
        );
      },
    );

    testWidgets(
      'shows "Calls" AppBar title when workspaceId is null',
      (WidgetTester tester) async {
        await tester.pumpWidget(_buildCallsScreenNoWorkspace());
        await tester.pump();

        expect(
          find.text('Calls'),
          findsOneWidget,
          reason: 'AppBar title "Calls" must be present in the no-workspace state',
        );
      },
    );

    testWidgets(
      'does NOT show "Start a Call" button when workspaceId is null',
      (WidgetTester tester) async {
        await tester.pumpWidget(_buildCallsScreenNoWorkspace());
        await tester.pump();

        expect(
          find.text('Start a Call'),
          findsNothing,
          reason:
              '"Start a Call" button must not be shown when no workspace is selected',
        );
      },
    );
  });

  // ---------------------------------------------------------------------------
  // Group 2: _loadRooms failure → error message and retry button
  //
  // Validates: Requirement 11.1
  // ---------------------------------------------------------------------------

  group('CallsScreen — _loadRooms failure (Req 11.1)', () {
    setUp(_setupSecureStorageMock);
    tearDown(_teardownSecureStorageMock);
    testWidgets(
      'shows error message when _loadRooms receives a non-200 response (Req 11.1)',
      (WidgetTester tester) async {
        await _withMockHttp(
          _FixedMockClient(statusCode: 500, body: 'Internal Server Error'),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.text('Failed to load rooms. Tap to retry.'),
              findsOneWidget,
              reason:
                  'CallsScreen must display an error message when _loadRooms '
                  'receives a non-200 response (Requirement 11.1)',
            );
          },
        );
      },
    );

    testWidgets(
      'shows Retry button when _loadRooms receives a non-200 response (Req 11.1)',
      (WidgetTester tester) async {
        await _withMockHttp(
          _FixedMockClient(statusCode: 503, body: 'Service Unavailable'),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.text('Retry'),
              findsOneWidget,
              reason:
                  'CallsScreen must display a Retry button when _loadRooms fails '
                  '(Requirement 11.1)',
            );
          },
        );
      },
    );

    testWidgets(
      'shows error message when _loadRooms throws a network exception (Req 11.1)',
      (WidgetTester tester) async {
        await _withMockHttp(
          _NetworkErrorMockClient(),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.text('Failed to load rooms. Tap to retry.'),
              findsOneWidget,
              reason:
                  'CallsScreen must display an error message when _loadRooms '
                  'throws a network exception (Requirement 11.1)',
            );
          },
        );
      },
    );

    testWidgets(
      'shows Retry button when _loadRooms throws a network exception (Req 11.1)',
      (WidgetTester tester) async {
        await _withMockHttp(
          _NetworkErrorMockClient(),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.text('Retry'),
              findsOneWidget,
              reason:
                  'CallsScreen must display a Retry button when _loadRooms throws '
                  'a network exception (Requirement 11.1)',
            );
          },
        );
      },
    );

    testWidgets(
      'does NOT show CircularProgressIndicator after _loadRooms fails',
      (WidgetTester tester) async {
        await _withMockHttp(
          _FixedMockClient(statusCode: 500, body: 'Error'),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            // The loading spinner must be gone once the error state is set.
            expect(
              find.byType(CircularProgressIndicator),
              findsNothing,
              reason:
                  'Loading spinner must not be shown after _loadRooms fails',
            );
          },
        );
      },
    );

    testWidgets(
      'Retry button re-triggers _loadRooms and clears the error state',
      (WidgetTester tester) async {
        // Phase 1: 500 → error state
        await _withMockHttp(
          _FixedMockClient(statusCode: 500, body: 'Error'),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.text('Failed to load rooms. Tap to retry.'),
              findsOneWidget,
            );
          },
        );

        // Phase 2: tap Retry with a successful response
        await _withMockHttp(
          _FixedMockClient(statusCode: 200, body: '[]'),
          () async {
            await tester.tap(find.text('Retry'));
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.text('Failed to load rooms. Tap to retry.'),
              findsNothing,
              reason: 'Error message must be cleared after a successful retry',
            );
          },
        );
      },
    );
  });

  // ---------------------------------------------------------------------------
  // Group 3: _startCall with missing room id → SnackBar, no navigation
  //
  // Validates: Requirement 11.5
  // ---------------------------------------------------------------------------

  group('CallsScreen — _startCall with missing room id (Req 11.5)', () {
    setUp(_setupSecureStorageMock);
    tearDown(_teardownSecureStorageMock);
    testWidgets(
      'shows SnackBar when _startCall response body has no "id" field (Req 11.5)',
      (WidgetTester tester) async {
        // GET /api/rooms/ → 200 empty list (renders main content with button)
        // POST /api/rooms/ → 201 with body missing the "id" key
        await _withMockHttp(
          _DispatchMockClient(
            getStatusCode: 200,
            getBody: '[]',
            postStatusCode: 201,
            postBody: jsonEncode({'name': 'Room 1'}), // no 'id' key
          ),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            // Main content must be visible
            expect(
              find.text('Start a Call'),
              findsOneWidget,
              reason: '"Start a Call" button must be present after rooms load',
            );

            await tester.tap(find.text('Start a Call'));
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.byType(SnackBar),
              findsOneWidget,
              reason:
                  'A SnackBar must be shown when the _startCall response body '
                  'does not contain a valid room id (Requirement 11.5)',
            );

            expect(
              find.text('Unexpected server response'),
              findsOneWidget,
              reason:
                  'SnackBar must display "Unexpected server response" when room '
                  'id is missing (Requirement 11.5)',
            );
          },
        );
      },
    );

    testWidgets(
      'does NOT navigate to VideoCallScreen when room id is missing (Req 11.5)',
      (WidgetTester tester) async {
        await _withMockHttp(
          _DispatchMockClient(
            getStatusCode: 200,
            getBody: '[]',
            postStatusCode: 201,
            postBody: jsonEncode({'name': 'Room 1'}), // no 'id' key
          ),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            await tester.tap(find.text('Start a Call'));
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.byType(VideoCallScreen),
              findsNothing,
              reason:
                  'CallsScreen must NOT navigate to VideoCallScreen when the '
                  'response body does not contain a valid room id (Requirement 11.5)',
            );
          },
        );
      },
    );

    testWidgets(
      'shows SnackBar when _startCall response body has null "id" (Req 11.5)',
      (WidgetTester tester) async {
        await _withMockHttp(
          _DispatchMockClient(
            getStatusCode: 200,
            getBody: '[]',
            postStatusCode: 201,
            postBody: jsonEncode({'id': null, 'name': 'Room 1'}), // explicit null
          ),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            await tester.tap(find.text('Start a Call'));
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.byType(SnackBar),
              findsOneWidget,
              reason:
                  'A SnackBar must be shown when the room id is explicitly null '
                  '(Requirement 11.5)',
            );

            expect(
              find.text('Unexpected server response'),
              findsOneWidget,
              reason:
                  'SnackBar must display "Unexpected server response" when room '
                  'id is null (Requirement 11.5)',
            );
          },
        );
      },
    );

    testWidgets(
      'does NOT navigate to VideoCallScreen when room id is null (Req 11.5)',
      (WidgetTester tester) async {
        await _withMockHttp(
          _DispatchMockClient(
            getStatusCode: 200,
            getBody: '[]',
            postStatusCode: 201,
            postBody: jsonEncode({'id': null, 'name': 'Room 1'}),
          ),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            await tester.tap(find.text('Start a Call'));
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.byType(VideoCallScreen),
              findsNothing,
              reason:
                  'CallsScreen must NOT navigate to VideoCallScreen when room '
                  'id is null (Requirement 11.5)',
            );
          },
        );
      },
    );

    testWidgets(
      'navigates to VideoCallScreen when _startCall returns a valid room id — control case (Req 11.4)',
      (WidgetTester tester) async {
        // Positive control: a valid room id must trigger navigation.
        await _withMockHttp(
          _DispatchMockClient(
            getStatusCode: 200,
            getBody: '[]',
            postStatusCode: 201,
            postBody: jsonEncode({'id': 'room-42', 'name': 'Room 42'}),
          ),
          () async {
            await tester.pumpWidget(_buildCallsScreenWithWorkspace());
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            await tester.tap(find.text('Start a Call'));
            // Use pump() rather than pumpAndSettle() to avoid waiting for
            // VideoCallScreen's WebSocket and WebRTC initialisation.
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 100));

            expect(
              find.byType(VideoCallScreen),
              findsOneWidget,
              reason:
                  'CallsScreen must navigate to VideoCallScreen when _startCall '
                  'returns a valid room id (Requirement 11.4)',
            );
          },
        );
      },
    );
  });
}
