/// Bug Condition Exploration Tests — Three Mobile App Bugs
///
/// **CRITICAL**: These tests MUST FAIL on unfixed code — failure confirms the bugs exist.
/// **DO NOT attempt to fix the tests or the code when they fail.**
/// **NOTE**: These tests encode the expected behavior — they will validate the fixes
///           when they pass after implementation.
/// **GOAL**: Surface counterexamples that demonstrate each bug exists.
///
/// **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3**
///
/// Expected counterexamples (on unfixed code):
/// - Bug 1: `loadWorkspaces()` is never called after `CreateWorkspaceScreen.pop(true)`
/// - Bug 2A: `_loading` is set to `false` with `_tasks = []` when `currentWorkspaceId` is `null`
/// - Bug 2B: `_load()` is not called when the user returns to the Tasks tab
/// - Bug 3: `NotiService.showNotification()` is not called after a 201 response

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/providers/workspace_provider.dart';
import 'package:mobile_app/screens/home/home_screen.dart';
import 'package:mobile_app/screens/tasks/tasks_screen.dart';
import 'package:mobile_app/screens/workspace/workspace_screen.dart';
import 'package:mobile_app/services/notification_service.dart';

// ---------------------------------------------------------------------------
// HTTP mocking helpers (same pattern as calls_screen_test.dart)
// ---------------------------------------------------------------------------

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

/// Dispatches GET vs POST to different responses.
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

/// Runs [body] inside an `http.runWithClient` zone so that all HTTP calls
/// made by ApiClient are intercepted by [client].
Future<void> _withMockHttp(
  http.Client client,
  Future<void> Function() body,
) async {
  await http.runWithClient(body, () => client);
}

// ---------------------------------------------------------------------------
// Secure storage mock (required for ApiClient._headers())
// ---------------------------------------------------------------------------

void _setupSecureStorageMock() {
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
    const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
    (MethodCall call) async => null,
  );
}

void _teardownSecureStorageMock() {
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
    const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
    null,
  );
}

// ---------------------------------------------------------------------------
// Fake WorkspaceNotifiers
// ---------------------------------------------------------------------------

/// Tracks calls to loadWorkspaces() without making real network requests.
class _TrackingWorkspaceNotifier extends WorkspaceNotifier {
  int loadWorkspacesCallCount = 0;

  _TrackingWorkspaceNotifier(WorkspaceState initialState) : super() {
    state = initialState;
  }

  @override
  Future<void> loadWorkspaces() async {
    loadWorkspacesCallCount++;
    // Do not call the real API — just record the call.
  }

  @override
  Future<void> switchWorkspace(String workspaceId) async {
    state = state.copyWith(currentWorkspaceId: workspaceId);
  }

  @override
  Future<void> loadChannels(String workspaceId) async {}

  /// Allows tests to push a new state (simulates workspace resolving).
  void pushState(WorkspaceState newState) {
    state = newState;
  }
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

// ---------------------------------------------------------------------------
// Fake NotiService — records showNotification() calls
// ---------------------------------------------------------------------------

class _FakeNotiService extends NotiService {
  final List<Map<String, String>> calls = [];

  _FakeNotiService() : super.forTesting();

  @override
  Future<void> initNotification() async {
    // no-op in tests
  }

  @override
  Future<void> showNotification({
    required String title,
    required String body,
  }) async {
    calls.add({'title': title, 'body': body});
  }
}

// ---------------------------------------------------------------------------
// Task JSON fixture
// ---------------------------------------------------------------------------

String _taskJson(String id, String title) => jsonEncode([
      {
        'id': id,
        'workspace_id': 'ws-test-1',
        'title': title,
        'description': '',
        'status': 'todo',
        'priority': 'medium',
        'assignee_id': null,
        'due_date': null,
        'created_at': '2024-01-01T00:00:00Z',
      }
    ]);

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  // =========================================================================
  // Bug 1: Workspace list not refreshing after creation
  //
  // Root cause: `_WorkspaceSwitcherSheet.onTap` for "Create New Workspace"
  // calls `Navigator.push(...)` without `await`, so the `bool?` result is
  // discarded and `loadWorkspaces()` is never triggered.
  //
  // Expected counterexample: `loadWorkspaces()` is never called after
  // `CreateWorkspaceScreen.pop(true)`.
  //
  // On UNFIXED code: FAILS — loadWorkspacesCallCount remains 0
  // On FIXED code:   PASSES — loadWorkspacesCallCount == 1
  //
  // **Validates: Requirements 1.1, 1.2, 1.3**
  // =========================================================================

  group('Bug 1: loadWorkspaces() called after CreateWorkspaceScreen pops with true', () {
    setUp(_setupSecureStorageMock);
    tearDown(_teardownSecureStorageMock);

    testWidgets(
      'Bug 1 exploration: loadWorkspaces() is called after workspace creation',
      (WidgetTester tester) async {
        // Arrange: tracking notifier starts with no workspaces
        final trackingNotifier = _TrackingWorkspaceNotifier(
          const WorkspaceState(
            workspaces: [],
            currentWorkspaceId: null,
          ),
        );

        // Mock HTTP: GET returns empty list; POST (create workspace) returns 201
        // so that CreateWorkspaceScreen pops with true after submission.
        await _withMockHttp(
          _DispatchMockClient(
            getStatusCode: 200,
            getBody: '[]',
            postStatusCode: 201,
            postBody: '{"id":"ws-new","name":"New WS","member_count":1}',
          ),
          () async {
            await tester.pumpWidget(
              ProviderScope(
                overrides: [
                  workspaceProvider.overrideWith((_) => trackingNotifier),
                ],
                child: MaterialApp(
                  home: HomeScreen(onSwitchTab: (_) {}),
                ),
              ),
            );

            await tester.pump();

            // Reset the call count after initState's loadWorkspaces() call
            trackingNotifier.loadWorkspacesCallCount = 0;

            // Act: open the workspace switcher sheet
            await tester.tap(find.byIcon(Icons.workspaces_outlined));
            await tester.pumpAndSettle();

            // Verify the sheet is open
            expect(find.text('Create New Workspace'), findsOneWidget);

            // Act: tap "Create New Workspace" — this pushes CreateWorkspaceScreen
            await tester.tap(find.text('Create New Workspace'));
            await tester.pumpAndSettle();

            // Verify we are now on the CreateWorkspaceScreen
            expect(find.text('Create Workspace'), findsWidgets);

            // Fill in the workspace name and submit
            await tester.enterText(find.byType(TextField).first, 'New WS');
            await tester.pump();
            await tester.tap(find.byType(ElevatedButton).first);
            await tester.pumpAndSettle();

            // CreateWorkspaceScreen receives 201 and pops with true.
            // On fixed code: the awaited push result is true, so loadWorkspaces()
            // is called. On unfixed code: the push was not awaited so the result
            // is discarded and loadWorkspaces() is never triggered.

            // Assert: loadWorkspaces() must have been called at least once
            // after the workspace creation screen returned.
            //
            // On UNFIXED code this FAILS because the push is not awaited and
            // loadWorkspaces() is never triggered from the switcher sheet.
            // (Note: CreateWorkspaceScreen also calls loadWorkspaces() internally
            //  on 201, so the total count may be >= 1.)
            expect(
              trackingNotifier.loadWorkspacesCallCount,
              greaterThanOrEqualTo(1),
              reason:
                  'Bug 1 counterexample: loadWorkspaces() was NOT called after '
                  'CreateWorkspaceScreen.pop(true). The Navigator.push is not '
                  'awaited so the result is discarded and the workspace list is '
                  'never refreshed.',
            );
          },
        );
      },
    );
  });

  // =========================================================================
  // Bug 2A: Race condition — TasksScreen shows empty state when
  // currentWorkspaceId is null at mount time
  //
  // Root cause: `initState` calls `_load()` synchronously. When
  // `currentWorkspaceId` is null, `_load()` sets `_loading = false` and
  // returns, causing the permanent empty state.
  //
  // Expected counterexample: `_loading` is set to `false` with `_tasks = []`
  // when `currentWorkspaceId` is `null`.
  //
  // On UNFIXED code: FAILS — empty state is shown permanently
  // On FIXED code:   PASSES — task list is shown after workspace resolves
  //
  // **Validates: Requirements 2.1, 2.2, 2.3**
  // =========================================================================

  group('Bug 2A: TasksScreen shows task list after workspace ID resolves (race condition)', () {
    setUp(_setupSecureStorageMock);
    tearDown(_teardownSecureStorageMock);

    testWidgets(
      'Bug 2A exploration: task list shown (not empty state) after workspace ID resolves',
      (WidgetTester tester) async {
        // Arrange: workspace starts with null currentWorkspaceId (race condition)
        final trackingNotifier = _TrackingWorkspaceNotifier(
          const WorkspaceState(
            workspaces: [],
            currentWorkspaceId: null, // <-- null at mount time (the bug condition)
          ),
        );

        await _withMockHttp(
          _FixedMockClient(
            statusCode: 200,
            body: _taskJson('task-1', 'Test Task'),
          ),
          () async {
            await tester.pumpWidget(
              ProviderScope(
                overrides: [
                  workspaceProvider.overrideWith((_) => trackingNotifier),
                ],
                child: const MaterialApp(home: TasksScreen()),
              ),
            );

            // Initial pump — workspace ID is null, _load() returns early
            await tester.pump();

            // Verify the initial state: loading spinner or empty state
            // (on unfixed code, empty state is shown immediately)

            // Simulate workspace resolving 100ms later (the race condition scenario)
            await tester.pump(const Duration(milliseconds: 100));

            // Now resolve the workspace ID (simulates workspaceProvider completing)
            trackingNotifier.pushState(
              const WorkspaceState(
                workspaces: [],
                currentWorkspaceId: 'ws-test-1', // workspace ID becomes available
              ),
            );

            // Allow didChangeDependencies / listeners to fire and _load() to complete
            await tester.pump();
            await tester.pump(const Duration(milliseconds: 50));
            await tester.pumpAndSettle();

            // Assert: the task list should be shown, NOT the empty state
            //
            // On UNFIXED code this FAILS because _loading was set to false
            // immediately when wsId was null, and the empty state is rendered
            // permanently — didChangeDependencies is never overridden to
            // re-trigger _load() when the workspace ID becomes available.
            expect(
              find.text('Test Task'),
              findsOneWidget,
              reason:
                  'Bug 2A counterexample: TasksScreen shows permanent empty state '
                  'when currentWorkspaceId is null at mount time. _loading is set '
                  'to false immediately with _tasks = [], and the empty state is '
                  'never replaced even after the workspace ID becomes available.',
            );
            expect(
              find.text('No tasks'),
              findsNothing,
              reason:
                  'Empty state must not be shown after workspace ID resolves.',
            );
          },
        );
      },
    );
  });

  // =========================================================================
  // Bug 2B: Stale list — TasksScreen does not re-fetch on tab re-focus
  //
  // Root cause: `TasksScreen` lives inside an `IndexedStack`, so `initState`
  // is never re-run when the user switches tabs. There is no
  // `didChangeDependencies` override to detect tab re-focus.
  //
  // Expected counterexample: `_load()` is not called when the user returns
  // to the Tasks tab.
  //
  // On UNFIXED code: FAILS — task list is stale after tab switch
  // On FIXED code:   PASSES — task list is refreshed on tab return
  //
  // **Validates: Requirements 2.1, 2.2, 2.3**
  // =========================================================================

  group('Bug 2B: TasksScreen re-fetches tasks when user returns to the Tasks tab', () {
    setUp(_setupSecureStorageMock);
    tearDown(_teardownSecureStorageMock);

    testWidgets(
      'Bug 2B exploration: updated task appears after tab switch and return',
      (WidgetTester tester) async {
        // Arrange: workspace has a valid ID from the start
        final trackingNotifier = _ValidWorkspaceNotifier();

        // Phase 1: initial load returns one task
        // Phase 2: after tab switch and return, a new task should appear
        int getCallCount = 0;

        final mockClient = _CountingMockClient(
          onSend: (request) {
            if (request.method.toUpperCase() == 'GET') {
              getCallCount++;
              if (getCallCount == 1) {
                // First load: return initial task
                return http.StreamedResponse(
                  Stream.value(utf8.encode(_taskJson('task-1', 'Initial Task'))),
                  200,
                  headers: {'content-type': 'application/json'},
                );
              } else {
                // Subsequent loads: return updated task list
                return http.StreamedResponse(
                  Stream.value(utf8.encode(jsonEncode([
                    {
                      'id': 'task-1',
                      'workspace_id': 'ws-test-1',
                      'title': 'Initial Task',
                      'description': '',
                      'status': 'todo',
                      'priority': 'medium',
                      'assignee_id': null,
                      'due_date': null,
                      'created_at': '2024-01-01T00:00:00Z',
                    },
                    {
                      'id': 'task-2',
                      'workspace_id': 'ws-test-1',
                      'title': 'New Task Added Elsewhere',
                      'description': '',
                      'status': 'todo',
                      'priority': 'medium',
                      'assignee_id': null,
                      'due_date': null,
                      'created_at': '2024-01-02T00:00:00Z',
                    },
                  ]))),
                  200,
                  headers: {'content-type': 'application/json'},
                );
              }
            }
            return http.StreamedResponse(
              Stream.value(utf8.encode('[]')),
              200,
              headers: {'content-type': 'application/json'},
            );
          },
        );

        await _withMockHttp(
          mockClient,
          () async {
            await tester.pumpWidget(
              ProviderScope(
                overrides: [
                  workspaceProvider.overrideWith((_) => trackingNotifier),
                ],
                child: const MaterialApp(
                  home: _TabSwitchHarness(),
                ),
              ),
            );

            // Initial load
            await tester.pumpAndSettle();

            // Verify initial task is shown
            expect(find.text('Initial Task'), findsOneWidget);
            expect(find.text('New Task Added Elsewhere'), findsNothing);

            final loadCountAfterMount = getCallCount;

            // Act: switch away from Tasks tab
            await tester.tap(find.text('Other'));
            await tester.pumpAndSettle();

            // Act: switch back to Tasks tab
            await tester.tap(find.text('Tasks'));
            await tester.pumpAndSettle();

            // Assert: _load() must have been called again (getCallCount increased)
            // AND the new task must be visible.
            //
            // On UNFIXED code this FAILS because _load() is only called in
            // initState and the IndexedStack keeps the widget alive without
            // rebuilding it. There is no didChangeDependencies override to
            // detect the tab re-focus.
            expect(
              getCallCount,
              greaterThan(loadCountAfterMount),
              reason:
                  'Bug 2B counterexample: _load() was NOT called when the user '
                  'returned to the Tasks tab. The IndexedStack keeps the widget '
                  'alive so initState is not re-run, and there is no '
                  'didChangeDependencies override to detect the tab re-focus.',
            );
            expect(
              find.text('New Task Added Elsewhere'),
              findsOneWidget,
              reason:
                  'New task must be visible after returning to the Tasks tab.',
            );
          },
        );
      },
    );
  });

  // =========================================================================
  // Bug 3: No local notification when a task is created
  //
  // Root cause:
  // 1. `NotiService.initNotification()` is never called at app startup.
  // 2. `_CreateTaskSheet` is a plain `StatefulWidget` with no `WidgetRef`.
  // 3. The `showNotification()` call is absent from `_create()`.
  //
  // Expected counterexample: `NotiService.showNotification()` is not called
  // after a 201 response.
  //
  // On UNFIXED code: FAILS — showNotification() is never called
  // On FIXED code:   PASSES — showNotification() is called with correct args
  //
  // **Validates: Requirements 3.1, 3.2, 3.3**
  // =========================================================================

  group('Bug 3: NotiService.showNotification() called after 201 response', () {
    setUp(_setupSecureStorageMock);
    tearDown(_teardownSecureStorageMock);

    testWidgets(
      'Bug 3 exploration: showNotification() called with title "Task Created" after 201',
      (WidgetTester tester) async {
        // Arrange: fake NotiService that records calls
        final fakeNotiService = _FakeNotiService();

        // Arrange: workspace has a valid ID
        final workspaceNotifier = _ValidWorkspaceNotifier();

        // Mock API: GET tasks returns empty list, POST tasks returns 201
        await _withMockHttp(
          _DispatchMockClient(
            getStatusCode: 200,
            getBody: '[]',
            postStatusCode: 201,
            postBody: jsonEncode({
              'id': 'task-new',
              'workspace_id': 'ws-test-1',
              'title': 'My New Task',
              'description': '',
              'status': 'todo',
              'priority': 'medium',
              'assignee_id': null,
              'due_date': null,
              'created_at': '2024-01-01T00:00:00Z',
            }),
          ),
          () async {
            await tester.pumpWidget(
              ProviderScope(
                overrides: [
                  workspaceProvider.overrideWith((_) => workspaceNotifier),
                  notiServiceProvider.overrideWithValue(fakeNotiService),
                ],
                child: const MaterialApp(home: TasksScreen()),
              ),
            );

            await tester.pumpAndSettle();

            // Act: tap the "+" button in the AppBar to open the create task sheet
            // Use the IconButton in the AppBar (not the ElevatedButton.icon in the empty state)
            await tester.tap(find.byIcon(Icons.add).first);
            await tester.pumpAndSettle();

            // Act: fill in the task title
            final titleField = find.byType(TextField).first;
            await tester.enterText(titleField, 'My New Task');
            await tester.pump();

            // Act: tap the "Create Task" submit button inside the sheet.
            // The empty-state "Create Task" button may also be in the tree
            // (behind the sheet), so we target the last match which is the
            // ElevatedButton inside the bottom sheet.
            await tester.tap(find.text('Create Task').last);
            await tester.pumpAndSettle();

            // Assert: showNotification() must have been called with correct args
            //
            // On UNFIXED code this FAILS because:
            // 1. _CreateTaskSheet is a plain StatefulWidget with no WidgetRef
            // 2. The showNotification() call is absent from _create()
            expect(
              fakeNotiService.calls,
              isNotEmpty,
              reason:
                  'Bug 3 counterexample: NotiService.showNotification() was NOT '
                  'called after a 201 response. _CreateTaskSheet is a plain '
                  'StatefulWidget with no WidgetRef, so it cannot access '
                  'notiServiceProvider, and the showNotification() call is '
                  'absent from _create().',
            );

            if (fakeNotiService.calls.isNotEmpty) {
              expect(
                fakeNotiService.calls.first['title'],
                equals('Task Created'),
                reason: 'Notification title must be "Task Created".',
              );
              expect(
                fakeNotiService.calls.first['body'],
                equals('My New Task'),
                reason: 'Notification body must equal the trimmed task title.',
              );
            }
          },
        );
      },
    );
  });
}

// ---------------------------------------------------------------------------
// Helper widgets
// ---------------------------------------------------------------------------

/// A screen that immediately pops with `true` when built.
/// Used to simulate CreateWorkspaceScreen completing successfully.
class _AutoPopTrueScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (Navigator.canPop(context)) {
        Navigator.pop(context, true);
      }
    });
    return const Scaffold(body: Center(child: Text('Creating...')));
  }
}

/// Simulates an IndexedStack with Tasks tab and Other tab.
/// Used for Bug 2B to test tab switching behavior.
class _TabSwitchHarness extends StatefulWidget {
  const _TabSwitchHarness();

  @override
  State<_TabSwitchHarness> createState() => _TabSwitchHarnessState();
}

class _TabSwitchHarnessState extends State<_TabSwitchHarness> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: const [
          TasksScreen(),
          Center(child: Text('Other Screen')),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.task),
            label: 'Tasks',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.home),
            label: 'Other',
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Counting mock HTTP client for Bug 2B
// ---------------------------------------------------------------------------

typedef _SendCallback = http.StreamedResponse Function(http.BaseRequest request);

class _CountingMockClient extends http.BaseClient {
  final _SendCallback onSend;

  _CountingMockClient({required this.onSend});

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return onSend(request);
  }
}
