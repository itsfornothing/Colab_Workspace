// Widget test for MainTabs index alignment
//
// Property 1: Tab index consistency
// For any index i in [0, 6], tapping the BottomNavigationBarItem at position i
// shall result in the IndexedStack displaying the child at index i.
//
// Validates: Requirements 1.3, 1.5

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/providers/auth_provider.dart';
import 'package:mobile_app/providers/workspace_provider.dart';
import 'package:mobile_app/providers/theme_provider.dart';
import 'package:mobile_app/models/user.dart';
import 'package:mobile_app/screens/main_tabs.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake StateNotifiers — return static state, never make network calls
// ─────────────────────────────────────────────────────────────────────────────

class _FakeAuthNotifier extends AuthNotifier {
  _FakeAuthNotifier()
      : super() {
    // Immediately set a logged-in user so screens don't redirect to login
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
    // Provide a minimal workspace state — no network calls
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
// Helper: build MainTabs with all providers overridden
// ─────────────────────────────────────────────────────────────────────────────

Widget _buildMainTabs() {
  return ProviderScope(
    overrides: [
      authProvider.overrideWith((_) => _FakeAuthNotifier()),
      workspaceProvider.overrideWith((_) => _FakeWorkspaceNotifier()),
      themeProvider.overrideWith((_) => _FakeThemeNotifier()),
    ],
    child: MaterialApp(
      home: const MainTabs(),
    ),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  // The nav item labels in order (indices 0–6)
  const navLabels = ['Home', 'Chat', 'Calls', 'Docs', 'Tasks', 'Files', 'Profile'];

  group('MainTabs — Property 1: Tab index consistency', () {
    // Validates: Requirements 1.3, 1.5
    //
    // For every index i in [0, 6], tapping the BottomNavigationBarItem at
    // position i must result in IndexedStack.index == i.

    for (int i = 0; i < navLabels.length; i++) {
      final index = i;
      final label = navLabels[i];

      testWidgets(
        'tapping nav item $index ("$label") sets IndexedStack.index to $index',
        (WidgetTester tester) async {
          await tester.pumpWidget(_buildMainTabs());
          // Allow initState callbacks and async work to settle
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));

          // Tap the BottomNavigationBarItem at the target index
          final navItem = find.text(label);
          expect(navItem, findsOneWidget,
              reason: 'BottomNavigationBarItem with label "$label" must exist');

          await tester.tap(navItem);
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));

          // Verify IndexedStack.index equals the tapped index.
          // Use .first because some child screens (e.g. TasksScreen's TabBarView)
          // may also contain an IndexedStack internally. The outermost one belongs
          // to MainTabs and is always the first in the widget tree.
          final indexedStack =
              tester.widget<IndexedStack>(find.byType(IndexedStack).first);
          expect(
            indexedStack.index,
            equals(index),
            reason:
                'After tapping nav item $index ("$label"), IndexedStack.index should be $index',
          );
        },
      );
    }

    testWidgets(
      'initial IndexedStack.index is 0 (Home tab)',
      (WidgetTester tester) async {
        await tester.pumpWidget(_buildMainTabs());
        await tester.pump();

        // Use .first — the outermost IndexedStack belongs to MainTabs
        final indexedStack =
            tester.widget<IndexedStack>(find.byType(IndexedStack).first);
        expect(indexedStack.index, equals(0),
            reason: 'MainTabs should start on the Home tab (index 0)');
      },
    );

    testWidgets(
      'IndexedStack has exactly 7 children matching the 7 nav items',
      (WidgetTester tester) async {
        await tester.pumpWidget(_buildMainTabs());
        await tester.pump();

        // Use .first — the outermost IndexedStack belongs to MainTabs
        final indexedStack =
            tester.widget<IndexedStack>(find.byType(IndexedStack).first);
        expect(indexedStack.children.length, equals(7),
            reason: 'IndexedStack must have exactly 7 children');

        // Also verify 7 nav items exist
        for (final label in navLabels) {
          expect(find.text(label), findsOneWidget,
              reason: 'BottomNavigationBarItem "$label" must be present');
        }
      },
    );

    testWidgets(
      'can switch between non-adjacent tabs correctly',
      (WidgetTester tester) async {
        await tester.pumpWidget(_buildMainTabs());
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        IndexedStack mainIndexedStack() =>
            tester.widget<IndexedStack>(find.byType(IndexedStack).first);

        // Go to Profile (6)
        await tester.tap(find.text('Profile'));
        await tester.pump();
        expect(mainIndexedStack().index, equals(6));

        // Go back to Home (0)
        await tester.tap(find.text('Home'));
        await tester.pump();
        expect(mainIndexedStack().index, equals(0));

        // Go to Calls (2)
        await tester.tap(find.text('Calls'));
        await tester.pump();
        expect(mainIndexedStack().index, equals(2));
      },
    );
  });
}
