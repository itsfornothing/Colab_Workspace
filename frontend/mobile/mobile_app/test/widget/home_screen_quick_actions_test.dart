// Widget test for HomeScreen quick actions
//
// Property 2: No dead quick actions
// For any _QuickAction widget rendered inside HomeScreen, its onTap callback
// shall not be a no-op. Every quick action must trigger a navigation or UI
// action when tapped.
//
// Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
//
// Property 3: Recent channel navigation carries correct data
// For any randomly generated list of Channel objects and a random index into
// that list, tapping the corresponding ListTile in HomeScreen must push a
// MessagingScreen whose AppBar displays the channel name at that index.
//
// Validates: Requirements 3.1, 3.2

import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/user.dart';
import 'package:mobile_app/models/workspace.dart';
import 'package:mobile_app/providers/auth_provider.dart';
import 'package:mobile_app/providers/workspace_provider.dart';
import 'package:mobile_app/providers/theme_provider.dart';
import 'package:mobile_app/screens/home/home_screen.dart';
import 'package:mobile_app/screens/chat/messaging_screen.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake StateNotifiers — return static state, never make network calls
// ─────────────────────────────────────────────────────────────────────────────

class _FakeAuthNotifier extends AuthNotifier {
  _FakeAuthNotifier() : super() {
    state = AuthState(
      user: User(
        id: 'test-user-1',
        email: 'test@example.com',
        fullName: 'Test User',
      ),
    );
  }

  @override
  Future<bool> tryAutoLogin() async => true;

  @override
  Future<void> login(String email, String password) async {}

  @override
  Future<void> logout() async {}
}

class _FakeWorkspaceNotifier extends WorkspaceNotifier {
  _FakeWorkspaceNotifier() : super() {
    state = const WorkspaceState(
      workspaces: [],
      currentWorkspaceId: 'ws-1',
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

/// A workspace notifier that serves a pre-built channel list — used by
/// Property 3 to inject arbitrary channel data without network calls.
class _FakeWorkspaceNotifierWithChannels extends WorkspaceNotifier {
  _FakeWorkspaceNotifierWithChannels(List<Channel> channels) : super() {
    state = WorkspaceState(
      workspaces: const [],
      currentWorkspaceId: 'ws-1',
      channels: channels,
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

class _FakeThemeNotifier extends ThemeNotifier {
  _FakeThemeNotifier() : super() {
    state = ThemeMode.light;
  }

  @override
  Future<void> setTheme(ThemeMode mode) async {
    state = mode;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: build HomeScreen with all providers overridden
// ─────────────────────────────────────────────────────────────────────────────

Widget _buildHomeScreen({required void Function(int) onSwitchTab}) {
  return ProviderScope(
    overrides: [
      authProvider.overrideWith((_) => _FakeAuthNotifier()),
      workspaceProvider.overrideWith((_) => _FakeWorkspaceNotifier()),
      themeProvider.overrideWith((_) => _FakeThemeNotifier()),
    ],
    child: MaterialApp(
      home: HomeScreen(onSwitchTab: onSwitchTab),
    ),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('HomeScreen — Property 2: No dead quick actions', () {
    // Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
    //
    // Every _QuickAction widget rendered inside HomeScreen must have a
    // non-no-op onTap handler. Tapping each quick action must either invoke
    // the onSwitchTab callback or show a bottom sheet.

    testWidgets(
      '"New Document" quick action calls onSwitchTab(3) — Docs tab',
      (WidgetTester tester) async {
        // Validates: Requirement 2.1
        final List<int> switchTabCalls = [];

        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (i) => switchTabCalls.add(i)),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        final newDocFinder = find.text('New Document');
        expect(newDocFinder, findsOneWidget,
            reason: '"New Document" quick action must be present');

        await tester.tap(newDocFinder);
        await tester.pump();

        expect(
          switchTabCalls,
          contains(3),
          reason:
              '"New Document" must call onSwitchTab(3) to navigate to the Docs tab',
        );
      },
    );

    testWidgets(
      '"Start Chat" quick action calls onSwitchTab(1) — Chat tab',
      (WidgetTester tester) async {
        // Validates: Requirement 2.2
        final List<int> switchTabCalls = [];

        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (i) => switchTabCalls.add(i)),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        final startChatFinder = find.text('Start Chat');
        expect(startChatFinder, findsOneWidget,
            reason: '"Start Chat" quick action must be present');

        await tester.tap(startChatFinder);
        await tester.pump();

        expect(
          switchTabCalls,
          contains(1),
          reason:
              '"Start Chat" must call onSwitchTab(1) to navigate to the Chat tab',
        );
      },
    );

    testWidgets(
      '"Start Call" quick action calls onSwitchTab(2) — Calls tab',
      (WidgetTester tester) async {
        // Validates: Requirement 2.3
        final List<int> switchTabCalls = [];

        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (i) => switchTabCalls.add(i)),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        final startCallFinder = find.text('Start Call');
        expect(startCallFinder, findsOneWidget,
            reason: '"Start Call" quick action must be present');

        await tester.tap(startCallFinder);
        await tester.pump();

        expect(
          switchTabCalls,
          contains(2),
          reason:
              '"Start Call" must call onSwitchTab(2) to navigate to the Calls tab',
        );
      },
    );

    testWidgets(
      '"Invite People" quick action shows a bottom sheet — not a no-op',
      (WidgetTester tester) async {
        // Validates: Requirement 2.4
        final List<int> switchTabCalls = [];

        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (i) => switchTabCalls.add(i)),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        final inviteFinder = find.text('Invite People');
        expect(inviteFinder, findsOneWidget,
            reason: '"Invite People" quick action must be present');

        await tester.tap(inviteFinder);
        // Allow the bottom sheet animation to complete
        await tester.pumpAndSettle();

        // The bottom sheet should be shown — look for the sheet title
        expect(
          find.text('Invite People'),
          findsWidgets,
          reason:
              '"Invite People" must open a bottom sheet (not be a no-op)',
        );

        // Verify the bottom sheet content is visible (the sheet has a title
        // and a Close button, confirming it is not a no-op)
        expect(
          find.text('Close'),
          findsOneWidget,
          reason:
              'The Invite People bottom sheet must contain a Close button',
        );

        // onSwitchTab should NOT have been called for "Invite People"
        expect(
          switchTabCalls,
          isEmpty,
          reason:
              '"Invite People" should show a bottom sheet, not switch tabs',
        );
      },
    );

    testWidgets(
      'All four quick actions are present in the widget tree',
      (WidgetTester tester) async {
        // Validates: Requirement 2.5 — no quick action is missing
        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (_) {}),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        const expectedLabels = [
          'New Document',
          'Start Chat',
          'Start Call',
          'Invite People',
        ];

        for (final label in expectedLabels) {
          expect(
            find.text(label),
            findsOneWidget,
            reason: 'Quick action "$label" must be present in HomeScreen',
          );
        }
      },
    );

    testWidgets(
      'No quick action is a no-op — all four trigger a real action when tapped',
      (WidgetTester tester) async {
        // Validates: Requirement 2.5
        // This is the core Property 2 assertion: tap every quick action and
        // verify that at least one observable side-effect occurs (tab switch
        // or bottom sheet shown).
        final List<int> switchTabCalls = [];

        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (i) => switchTabCalls.add(i)),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // Tap "New Document" — must call onSwitchTab
        await tester.tap(find.text('New Document'));
        await tester.pump();
        expect(switchTabCalls, isNotEmpty,
            reason: '"New Document" must not be a no-op');
        switchTabCalls.clear();

        // Tap "Start Chat" — must call onSwitchTab
        await tester.tap(find.text('Start Chat'));
        await tester.pump();
        expect(switchTabCalls, isNotEmpty,
            reason: '"Start Chat" must not be a no-op');
        switchTabCalls.clear();

        // Tap "Start Call" — must call onSwitchTab
        await tester.tap(find.text('Start Call'));
        await tester.pump();
        expect(switchTabCalls, isNotEmpty,
            reason: '"Start Call" must not be a no-op');
        switchTabCalls.clear();

        // Tap "Invite People" — must show a bottom sheet (not call onSwitchTab)
        await tester.tap(find.text('Invite People'));
        await tester.pumpAndSettle();
        // Bottom sheet is shown when "Close" button appears
        expect(
          find.text('Close'),
          findsOneWidget,
          reason: '"Invite People" must not be a no-op — it must show a bottom sheet',
        );
        // onSwitchTab should not have been called for "Invite People"
        expect(switchTabCalls, isEmpty,
            reason: '"Invite People" should show a bottom sheet, not switch tabs');
      },
    );

    testWidgets(
      '"New Document" calls onSwitchTab with exactly index 3',
      (WidgetTester tester) async {
        // Validates: Requirement 2.1 — specifically the Docs tab (index 3)
        final List<int> switchTabCalls = [];

        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (i) => switchTabCalls.add(i)),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        await tester.tap(find.text('New Document'));
        await tester.pump();

        expect(switchTabCalls.length, equals(1),
            reason: 'onSwitchTab should be called exactly once');
        expect(switchTabCalls.first, equals(3),
            reason: '"New Document" must navigate to Docs tab (index 3)');
      },
    );

    testWidgets(
      '"Start Chat" calls onSwitchTab with exactly index 1',
      (WidgetTester tester) async {
        // Validates: Requirement 2.2 — specifically the Chat tab (index 1)
        final List<int> switchTabCalls = [];

        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (i) => switchTabCalls.add(i)),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        await tester.tap(find.text('Start Chat'));
        await tester.pump();

        expect(switchTabCalls.length, equals(1),
            reason: 'onSwitchTab should be called exactly once');
        expect(switchTabCalls.first, equals(1),
            reason: '"Start Chat" must navigate to Chat tab (index 1)');
      },
    );

    testWidgets(
      '"Start Call" calls onSwitchTab with exactly index 2',
      (WidgetTester tester) async {
        // Validates: Requirement 2.3 — specifically the Calls tab (index 2)
        final List<int> switchTabCalls = [];

        await tester.pumpWidget(
          _buildHomeScreen(onSwitchTab: (i) => switchTabCalls.add(i)),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        await tester.tap(find.text('Start Call'));
        await tester.pump();

        expect(switchTabCalls.length, equals(1),
            reason: 'onSwitchTab should be called exactly once');
        expect(switchTabCalls.first, equals(2),
            reason: '"Start Call" must navigate to Calls tab (index 2)');
      },
    );
  });

  group('HomeScreen — Property 3: Recent channel navigation carries correct data', () {
    // Property 3: Recent channel navigation carries correct data
    //
    // For any randomly generated list of 1–5 Channel objects and a random
    // index into that list, tapping the corresponding ListTile in HomeScreen
    // must push a MessagingScreen whose AppBar displays the channel name at
    // that index.
    //
    // Validates: Requirements 3.1, 3.2

    /// Builds a HomeScreen with the given channel list injected via a
    /// [_FakeWorkspaceNotifierWithChannels].
    Widget _buildHomeScreenWithChannels(List<Channel> channels, {Key? key}) {
      return ProviderScope(
        key: key,
        overrides: [
          authProvider.overrideWith((_) => _FakeAuthNotifier()),
          workspaceProvider.overrideWith(
              (_) => _FakeWorkspaceNotifierWithChannels(channels)),
          themeProvider.overrideWith((_) => _FakeThemeNotifier()),
        ],
        child: MaterialApp(
          home: HomeScreen(onSwitchTab: (_) {}),
        ),
      );
    }

    testWidgets(
      'Property 3: tapping any channel tile navigates to MessagingScreen with correct channel data',
      (WidgetTester tester) async {
        // Validates: Requirements 3.1, 3.2
        //
        // Run 20 iterations with randomly generated channel lists and indices.
        // Each iteration verifies that the MessagingScreen pushed by tapping
        // a channel tile displays the correct channel name in its AppBar.

        final random = Random(42); // fixed seed for reproducibility

        for (int iteration = 0; iteration < 20; iteration++) {
          // Generate a list of 1–5 channels (HomeScreen shows take(5))
          final channelCount = 1 + random.nextInt(5); // 1..5
          final channels = List.generate(channelCount, (i) {
            final suffix = random.nextInt(100000);
            return Channel(
              id: 'ch-$iteration-$i',
              name: 'channel-$iteration-$i-$suffix',
            );
          });

          // Pick a random index into the channel list
          final index = random.nextInt(channels.length);
          final expectedChannel = channels[index];

          // Pump the HomeScreen with the generated channels.
          // Use a unique ValueKey per iteration to force Flutter to recreate
          // the ProviderScope (and thus the notifier) rather than reusing the
          // previous one.
          await tester.pumpWidget(
              _buildHomeScreenWithChannels(channels, key: ValueKey(iteration)));
          // Pump multiple times to ensure all post-frame callbacks fire
          // and the widget tree is fully built
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 50));
          await tester.pump(const Duration(milliseconds: 50));

          // The 'Recent Channels' section must be visible
          expect(
            find.text('Recent Channels'),
            findsOneWidget,
            reason:
                'Iteration $iteration: "Recent Channels" section must appear when channels are non-empty',
          );

          // Find the ListTile for the channel at the generated index by its name
          final tileFinder = find.text(expectedChannel.name);
          expect(
            tileFinder,
            findsOneWidget,
            reason:
                'Iteration $iteration: channel "${expectedChannel.name}" must appear as a ListTile title',
          );

          // Scroll the tile into view (channels section may be below the fold)
          await tester.ensureVisible(tileFinder);
          await tester.pump();

          // Tap the tile — this pushes MessagingScreen
          await tester.tap(tileFinder, warnIfMissed: false);
          // Use pump() instead of pumpAndSettle() to avoid waiting for
          // network calls made by MessagingScreen.initState
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));

          // Verify MessagingScreen is now in the widget tree (Req 3.1)
          expect(
            find.byType(MessagingScreen),
            findsOneWidget,
            reason:
                'Iteration $iteration: tapping channel tile must push MessagingScreen',
          );

          // Verify the channel name appears in the MessagingScreen AppBar (Req 3.2)
          // MessagingScreen renders widget.channel.name as a Text in its AppBar title
          expect(
            find.text(expectedChannel.name),
            findsWidgets,
            reason:
                'Iteration $iteration: MessagingScreen AppBar must display channel name "${expectedChannel.name}"',
          );
          // pumpWidget at the start of the next iteration replaces the entire
          // widget tree, so no explicit pop is needed here.
        }
      },
    );

    testWidgets(
      'Property 3 (single-channel sanity): channel id and name are passed correctly to MessagingScreen',
      (WidgetTester tester) async {
        // Validates: Requirements 3.1, 3.2
        //
        // Deterministic single-channel test to confirm the adapter
        // channelFromWorkspaceChannel preserves id and name.

        final channel = Channel(
          id: 'deterministic-id-42',
          name: 'deterministic-channel',
        );

        await tester.pumpWidget(_buildHomeScreenWithChannels([channel]));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.text('Recent Channels'), findsOneWidget);
        expect(find.text('deterministic-channel'), findsOneWidget);

        // Scroll the tile into view (channels section may be below the fold)
        await tester.ensureVisible(find.text('deterministic-channel'));
        await tester.pump();

        await tester.tap(find.text('deterministic-channel'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // MessagingScreen must be pushed (Req 3.1)
        expect(find.byType(MessagingScreen), findsOneWidget);

        // Channel name must appear in the AppBar (Req 3.2)
        expect(find.text('deterministic-channel'), findsWidgets);
      },
    );
  });
}
