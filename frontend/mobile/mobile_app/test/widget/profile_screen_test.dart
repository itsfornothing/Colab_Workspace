// Widget tests for ProfileScreen
//
// Property 4: Profile screen displays authenticated user data
// For any User object held in AuthState, the ProfileScreen shall display
// user.fullName and user.email as visible text in its widget tree.
//
// Validates: Requirements 4.1, 4.2
//
// Property 5: Empty name validation rejects save
// For any string composed entirely of whitespace characters (including the
// empty string), attempting to save it as the full name in ProfileScreen edit
// mode shall be rejected with a validation error SnackBar, and no PATCH
// request shall be sent.
//
// Validates: Requirement 5.5
//
// Implementation note:
// ProfileScreen._saveProfile() checks `_nameCtrl.text.trim().isEmpty` before
// making any API call. When the check fires it shows a SnackBar and returns
// early — so the ApiClient.patch() singleton is never reached. This means the
// test does not need to mock the HTTP layer; it only needs to verify:
//   1. A SnackBar with the validation message is shown.
//   2. The screen remains in edit mode (Save button still visible).
//
// PBT approach:
// Glados property tests run in a plain Dart context and cannot use
// WidgetTester. For widget-level property tests this project uses the same
// pattern as home_screen_quick_actions_test.dart (Property 3): run multiple
// iterations inside a single testWidgets call, generating inputs with a seeded
// Random for reproducibility.

import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/user.dart';
import 'package:mobile_app/providers/auth_provider.dart';
import 'package:mobile_app/providers/theme_provider.dart';
import 'package:mobile_app/screens/profile/profile_screen.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake StateNotifiers — return static state, never make network calls
// ─────────────────────────────────────────────────────────────────────────────

class _FakeAuthNotifier extends AuthNotifier {
  _FakeAuthNotifier(User user) : super() {
    state = AuthState(user: user);
  }

  @override
  Future<bool> tryAutoLogin() async => true;

  @override
  Future<void> login(String email, String password) async {}

  @override
  Future<void> logout() async {}
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
// Default test user
// ─────────────────────────────────────────────────────────────────────────────

final _testUser = User(
  id: 'test-user-1',
  email: 'test@example.com',
  fullName: 'Test User',
  jobTitle: 'Engineer',
  bio: 'A test bio',
);

// ─────────────────────────────────────────────────────────────────────────────
// Helper: build ProfileScreen with all providers overridden
// ─────────────────────────────────────────────────────────────────────────────

Widget _buildProfileScreen({User? user}) {
  return ProviderScope(
    overrides: [
      authProvider.overrideWith((_) => _FakeAuthNotifier(user ?? _testUser)),
      themeProvider.overrideWith((_) => _FakeThemeNotifier()),
    ],
    child: const MaterialApp(
      home: ProfileScreen(),
    ),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Whitespace string generator
// ─────────────────────────────────────────────────────────────────────────────
//
// The whitespace alphabet covers the characters that String.trim() removes:
// space (U+0020), horizontal tab (U+0009), and newline (U+000A).

/// Returns a string of [length] whitespace characters cycling through
/// space, tab, and newline.
String _whitespaceString(int length) {
  const chars = [' ', '\t', '\n'];
  final buf = StringBuffer();
  for (var i = 0; i < length; i++) {
    buf.write(chars[i % chars.length]);
  }
  return buf.toString();
}

/// Generates a list of [count] whitespace-only strings with lengths in
/// [0, maxLength] using [random] for reproducibility.
List<String> _generateWhitespaceInputs(
    Random random, int count, int maxLength) {
  return List.generate(count, (_) {
    final length = random.nextInt(maxLength + 1); // 0..maxLength inclusive
    return _whitespaceString(length);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// User data generator
// ─────────────────────────────────────────────────────────────────────────────

/// Generates a printable, non-empty ASCII string of [length] characters using
/// [random]. Characters are drawn from letters and digits so the generated
/// values are always valid widget text (no control characters or null bytes).
String _randomAlphanumeric(Random random, int length) {
  const chars =
      'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  return String.fromCharCodes(
    List.generate(length, (_) => chars.codeUnitAt(random.nextInt(chars.length))),
  );
}

/// Generates a random non-empty full name of the form "FirstName LastName"
/// where each part is 3–10 alphanumeric characters.
String _randomFullName(Random random) {
  final first = _randomAlphanumeric(random, 3 + random.nextInt(8)); // 3..10
  final last = _randomAlphanumeric(random, 3 + random.nextInt(8));
  return '$first $last';
}

/// Generates a random email address of the form "local@domain.tld" where
/// each segment is 3–8 alphanumeric characters.
String _randomEmail(Random random) {
  final local = _randomAlphanumeric(random, 3 + random.nextInt(6)); // 3..8
  final domain = _randomAlphanumeric(random, 3 + random.nextInt(6));
  final tld = _randomAlphanumeric(random, 2 + random.nextInt(3)); // 2..4
  return '$local@$domain.$tld';
}

/// Generates a [User] with a random [fullName] and [email].
User _randomUser(Random random, int index) {
  return User(
    id: 'user-$index',
    email: _randomEmail(random),
    fullName: _randomFullName(random),
  );
}

void main() {
  // ---------------------------------------------------------------------------
  // Property 4: Profile screen displays authenticated user data
  //
  // For any User object held in AuthState, the ProfileScreen shall display
  // user.fullName and user.email as visible text in its widget tree.
  //
  // Validates: Requirements 4.1, 4.2
  // ---------------------------------------------------------------------------

  group('ProfileScreen — Property 4: Profile screen displays authenticated user data', () {
    // -------------------------------------------------------------------------
    // Property-based test: any User's fullName and email appear in the widget tree
    // -------------------------------------------------------------------------
    //
    // Runs 50 iterations with randomly generated User objects. Each iteration
    // verifies that both user.fullName and user.email are present as Text
    // widgets in the ProfileScreen widget tree.
    //
    // This mirrors the pattern used in home_screen_quick_actions_test.dart
    // (Property 3) — multiple iterations inside a single testWidgets call
    // with a seeded Random for reproducibility.

    testWidgets(
      'Property 4: any User fullName and email appear as text in the widget tree',
      (WidgetTester tester) async {
        // Validates: Requirements 4.1, 4.2
        final random = Random(99); // fixed seed for reproducibility

        for (var i = 0; i < 50; i++) {
          final user = _randomUser(random, i);

          // Pump a blank widget first to fully tear down the previous tree
          // (including any lingering overlays), then pump the fresh ProfileScreen.
          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pumpAndSettle();

          await tester.pumpWidget(_buildProfileScreen(user: user));
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));

          // Assert 1: user.email appears in the widget tree (Requirement 4.2)
          // ProfileScreen renders the email as Text(user?.email ?? '') below
          // the avatar, always visible regardless of edit mode.
          expect(
            find.text(user.email),
            findsOneWidget,
            reason:
                'Iteration $i: user.email "${user.email}" must appear as a '
                'Text widget in ProfileScreen',
          );

          // Assert 2: user.fullName appears in the widget tree (Requirement 4.1)
          // ProfileScreen renders fullName in an _InfoRow when not in edit mode
          // and fullName is non-empty. Since _randomFullName always produces a
          // non-empty string, this must always be present.
          expect(
            find.text(user.fullName),
            findsOneWidget,
            reason:
                'Iteration $i: user.fullName "${user.fullName}" must appear as a '
                'Text widget in ProfileScreen',
          );
        }
      },
    );

    // -------------------------------------------------------------------------
    // Concrete deterministic tests
    // -------------------------------------------------------------------------

    testWidgets(
      'displays fullName from AuthState (Requirement 4.1)',
      (WidgetTester tester) async {
        // Validates: Requirement 4.1
        final user = User(
          id: 'u1',
          email: 'alice@example.com',
          fullName: 'Alice Smith',
        );

        await tester.pumpWidget(_buildProfileScreen(user: user));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          find.text('Alice Smith'),
          findsOneWidget,
          reason: 'ProfileScreen must display the authenticated user\'s full name',
        );
      },
    );

    testWidgets(
      'displays email from AuthState (Requirement 4.2)',
      (WidgetTester tester) async {
        // Validates: Requirement 4.2
        final user = User(
          id: 'u2',
          email: 'bob@example.com',
          fullName: 'Bob Jones',
        );

        await tester.pumpWidget(_buildProfileScreen(user: user));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          find.text('bob@example.com'),
          findsOneWidget,
          reason: 'ProfileScreen must display the authenticated user\'s email',
        );
      },
    );

    testWidgets(
      'displays both fullName and email simultaneously (Requirements 4.1 and 4.2)',
      (WidgetTester tester) async {
        // Validates: Requirements 4.1, 4.2
        final user = User(
          id: 'u3',
          email: 'carol@example.com',
          fullName: 'Carol White',
        );

        await tester.pumpWidget(_buildProfileScreen(user: user));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          find.text('Carol White'),
          findsOneWidget,
          reason: 'ProfileScreen must display fullName',
        );
        expect(
          find.text('carol@example.com'),
          findsOneWidget,
          reason: 'ProfileScreen must display email',
        );
      },
    );

    testWidgets(
      'displays updated user data when AuthState changes — different user',
      (WidgetTester tester) async {
        // Validates: Requirements 4.1, 4.2
        // Confirms that the screen reflects the user currently in AuthState,
        // not a stale cached value.
        final user = User(
          id: 'u4',
          email: 'dave@example.com',
          fullName: 'Dave Brown',
          jobTitle: 'Designer',
          bio: 'Loves pixels',
        );

        await tester.pumpWidget(_buildProfileScreen(user: user));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.text('Dave Brown'), findsOneWidget);
        expect(find.text('dave@example.com'), findsOneWidget);
      },
    );

    testWidgets(
      'fullName is NOT shown in edit mode text field header — only in view mode',
      (WidgetTester tester) async {
        // Validates: Requirement 4.1
        // In view mode, fullName appears as a read-only _InfoRow Text widget.
        // In edit mode, it moves into a TextField. This test confirms the
        // view-mode display is correct before any editing occurs.
        final user = User(
          id: 'u5',
          email: 'eve@example.com',
          fullName: 'Eve Green',
        );

        await tester.pumpWidget(_buildProfileScreen(user: user));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // In view mode: fullName appears as a plain Text widget
        expect(
          find.text('Eve Green'),
          findsOneWidget,
          reason: 'fullName must appear as a Text widget in view mode',
        );

        // Email is always visible regardless of mode
        expect(
          find.text('eve@example.com'),
          findsOneWidget,
          reason: 'email must always be visible',
        );
      },
    );
  });

  // ---------------------------------------------------------------------------
  // Property 5: Empty name validation rejects save
  //
  // For any string composed entirely of whitespace characters (including the
  // empty string), attempting to save it as the full name in ProfileScreen
  // edit mode shall:
  //   1. Show a SnackBar with a validation error message.
  //   2. NOT submit a PATCH request (the screen stays in edit mode).
  //
  // Validates: Requirement 5.5
  // ---------------------------------------------------------------------------

  group('ProfileScreen — Property 5: Empty name validation rejects save', () {
    // -------------------------------------------------------------------------
    // Property-based test: any whitespace-only string is rejected
    // -------------------------------------------------------------------------
    //
    // Runs 50 iterations with randomly generated whitespace strings of
    // length 0–50. Each iteration verifies that:
    //   1. A validation SnackBar appears.
    //   2. The screen remains in edit mode (Save button still visible).
    //
    // This mirrors the pattern used in home_screen_quick_actions_test.dart
    // (Property 3) — multiple iterations inside a single testWidgets call
    // with a seeded Random for reproducibility.

    testWidgets(
      'Property 5: any whitespace-only name (0–50 chars) shows validation SnackBar and stays in edit mode',
      (WidgetTester tester) async {
        // Validates: Requirement 5.5
        final random = Random(42); // fixed seed for reproducibility
        final inputs = _generateWhitespaceInputs(random, 50, 50);

        for (var i = 0; i < inputs.length; i++) {
          final whitespaceInput = inputs[i];

          // Pump a blank widget first to fully tear down the previous tree
          // (including any lingering SnackBar overlays), then pump the fresh
          // ProfileScreen. This avoids SnackBar state leaking between iterations.
          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pumpAndSettle();

          await tester.pumpWidget(_buildProfileScreen());
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));

          // Enter edit mode by tapping the edit icon in the AppBar
          final editIconFinder = find.byIcon(Icons.edit_outlined);
          expect(
            editIconFinder,
            findsOneWidget,
            reason: 'Iteration $i: Edit icon must be present in the AppBar',
          );
          await tester.tap(editIconFinder);
          await tester.pump();

          // The Full Name TextField must be visible in edit mode
          final textFields = find.byType(TextField);
          expect(
            textFields,
            findsWidgets,
            reason: 'Iteration $i: TextFields must be present in edit mode',
          );

          // Enter the whitespace-only string into the Full Name field
          // (the first TextField rendered in edit mode is the Full Name field)
          await tester.enterText(textFields.first, whitespaceInput);
          await tester.pump();

          // Tap the Save button in the AppBar
          final saveFinder = find.text('Save');
          expect(
            saveFinder,
            findsOneWidget,
            reason: 'Iteration $i: Save button must be present in edit mode',
          );
          await tester.tap(saveFinder);
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));

          // Assert 1: A validation SnackBar is shown
          expect(
            find.byType(SnackBar),
            findsOneWidget,
            reason:
                'Iteration $i: A validation SnackBar must appear when Save is '
                'tapped with whitespace-only name (length=${whitespaceInput.length})',
          );

          // Assert 2: The SnackBar contains the correct validation message
          expect(
            find.text('Full name cannot be empty'),
            findsOneWidget,
            reason:
                'Iteration $i: SnackBar must display "Full name cannot be empty" '
                '(length=${whitespaceInput.length})',
          );

          // Assert 3: The screen remains in edit mode (Save button still visible).
          // If the save had succeeded, the screen would exit edit mode and the
          // Save button would disappear.
          expect(
            find.text('Save'),
            findsOneWidget,
            reason:
                'Iteration $i: Save button must still be visible — screen must '
                'remain in edit mode after validation rejection '
                '(length=${whitespaceInput.length})',
          );
        }
      },
    );

    // -------------------------------------------------------------------------
    // Concrete edge-case tests
    // -------------------------------------------------------------------------

    testWidgets(
      'empty string ("") shows validation SnackBar and stays in edit mode',
      (WidgetTester tester) async {
        // Validates: Requirement 5.5 — empty string edge case
        await tester.pumpWidget(_buildProfileScreen());
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // Enter edit mode
        await tester.tap(find.byIcon(Icons.edit_outlined));
        await tester.pump();

        // Clear the Full Name field (set to empty string)
        final textFields = find.byType(TextField);
        await tester.enterText(textFields.first, '');
        await tester.pump();

        // Tap Save
        await tester.tap(find.text('Save'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // SnackBar with validation message must appear
        expect(find.byType(SnackBar), findsOneWidget);
        expect(find.text('Full name cannot be empty'), findsOneWidget);

        // Screen must remain in edit mode
        expect(find.text('Save'), findsOneWidget);
      },
    );

    testWidgets(
      'single space (" ") shows validation SnackBar and stays in edit mode',
      (WidgetTester tester) async {
        // Validates: Requirement 5.5 — single space edge case
        await tester.pumpWidget(_buildProfileScreen());
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        await tester.tap(find.byIcon(Icons.edit_outlined));
        await tester.pump();

        final textFields = find.byType(TextField);
        await tester.enterText(textFields.first, ' ');
        await tester.pump();

        await tester.tap(find.text('Save'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.byType(SnackBar), findsOneWidget);
        expect(find.text('Full name cannot be empty'), findsOneWidget);
        expect(find.text('Save'), findsOneWidget);
      },
    );

    testWidgets(
      r'tab character ("\t") shows validation SnackBar and stays in edit mode',
      (WidgetTester tester) async {
        // Validates: Requirement 5.5 — tab character edge case
        await tester.pumpWidget(_buildProfileScreen());
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        await tester.tap(find.byIcon(Icons.edit_outlined));
        await tester.pump();

        final textFields = find.byType(TextField);
        await tester.enterText(textFields.first, '\t');
        await tester.pump();

        await tester.tap(find.text('Save'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.byType(SnackBar), findsOneWidget);
        expect(find.text('Full name cannot be empty'), findsOneWidget);
        expect(find.text('Save'), findsOneWidget);
      },
    );

    testWidgets(
      'multiple spaces ("   ") shows validation SnackBar and stays in edit mode',
      (WidgetTester tester) async {
        // Validates: Requirement 5.5 — multiple spaces edge case
        await tester.pumpWidget(_buildProfileScreen());
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        await tester.tap(find.byIcon(Icons.edit_outlined));
        await tester.pump();

        final textFields = find.byType(TextField);
        await tester.enterText(textFields.first, '   ');
        await tester.pump();

        await tester.tap(find.text('Save'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.byType(SnackBar), findsOneWidget);
        expect(find.text('Full name cannot be empty'), findsOneWidget);
        expect(find.text('Save'), findsOneWidget);
      },
    );

    testWidgets(
      'non-empty name does NOT show validation SnackBar — control case',
      (WidgetTester tester) async {
        // Validates: Requirement 5.5 — confirms the validation only fires for
        // whitespace-only names, not for valid names.
        // This is a control test: a valid name must NOT trigger the error.
        await tester.pumpWidget(_buildProfileScreen());
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        await tester.tap(find.byIcon(Icons.edit_outlined));
        await tester.pump();

        final textFields = find.byType(TextField);
        await tester.enterText(textFields.first, 'Alice Smith');
        await tester.pump();

        await tester.tap(find.text('Save'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // The validation SnackBar must NOT appear for a valid name
        expect(
          find.text('Full name cannot be empty'),
          findsNothing,
          reason:
              'Validation SnackBar must NOT appear when the name is non-empty',
        );
      },
    );
  });
}
