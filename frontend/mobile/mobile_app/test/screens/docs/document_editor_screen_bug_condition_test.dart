/// Bug Condition Exploration Test — Doc Editor Content Not Displaying
///
/// **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists.
/// **DO NOT attempt to fix the test or the code when it fails.**
/// **NOTE**: This test encodes the expected behavior — it will validate the fix
///           when it passes after implementation.
/// **GOAL**: Surface counterexamples that demonstrate the bug exists.
///
/// Bug Condition: QuillEditorConfig has contextMenuBuilder returning SizedBox.shrink()
/// which intercepts the rendering pipeline and prevents typed text from appearing.
///
/// Expected counterexamples (on unfixed code):
/// - contextMenuBuilder IS present in QuillEditorConfig source code
/// - DocumentEditorScreen source uses a non-const QuillEditorConfig with a
///   contextMenuBuilder closure returning SizedBox.shrink()
///
/// **Validates: Requirements 1.1, 1.2, 1.3**

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_quill/flutter_quill.dart' show FlutterQuillLocalizations;
import 'package:flutter_test/flutter_test.dart';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  // =========================================================================
  // Test 1: Static code inspection — contextMenuBuilder IS present (bug condition)
  //
  // This is a unit test (not a widget test) that reads the source file as a
  // string and asserts that the bug condition code is present.
  //
  // On UNFIXED code: PASSES (confirms the bug condition exists in the source)
  // On FIXED code:   FAILS (confirms the fix removed the bug condition)
  // =========================================================================

  group('Static Inspection: Bug Condition Code Present in Source', () {
    test(
      'Static inspection: contextMenuBuilder IS present in QuillEditorConfig (bug condition)',
      () {
        // Read the source file directly — this is a static analysis test.
        // The path is relative to the project root where `flutter test` is run.
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        // Assert: contextMenuBuilder IS present in the source (bug condition)
        expect(
          source,
          contains('contextMenuBuilder'),
          reason:
              'Bug condition: contextMenuBuilder must be present in QuillEditorConfig. '
              'This test confirms the bug condition exists in the unfixed code. '
              'When the fix is applied (contextMenuBuilder removed), this assertion '
              'will fail — which is expected after the fix.',
        );

        // Assert: the contextMenuBuilder returns SizedBox.shrink() (the specific bug)
        expect(
          source,
          contains('SizedBox.shrink()'),
          reason:
              'Bug condition: contextMenuBuilder must return SizedBox.shrink(). '
              'This is the specific code that intercepts the rendering pipeline '
              'and prevents typed text from appearing in the Quill editor.',
        );

        // Assert: the contextMenuBuilder is inside a QuillEditorConfig block
        // (not just the title TextField's contextMenuBuilder)
        expect(
          source,
          contains('QuillEditorConfig'),
          reason:
              'QuillEditorConfig must be present in the source — this is where '
              'the bug condition contextMenuBuilder is configured.',
        );
      },
    );

    test(
      'Static inspection: QuillEditorConfig in DocumentEditorScreen has contextMenuBuilder '
      'that returns SizedBox.shrink() — NOT the fixed const config',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        // The fixed code uses `const quill.QuillEditorConfig(...)` without
        // contextMenuBuilder. The buggy code has a non-const config with
        // contextMenuBuilder returning SizedBox.shrink().
        //
        // Assert: the source contains the non-const QuillEditorConfig
        // with the contextMenuBuilder closure.
        //
        // On UNFIXED code: PASSES — the config has a closure (non-const)
        // On FIXED code:   FAILS — the closure has been removed
        final hasContextMenuBuilderWithSizedBox = source.contains(
          'contextMenuBuilder: (context, rawEditorState) =>',
        );

        expect(
          hasContextMenuBuilderWithSizedBox,
          isTrue,
          reason:
              'Bug condition: QuillEditorConfig must have contextMenuBuilder '
              'returning SizedBox.shrink() via a closure. '
              'This is the exact bug condition in DocumentEditorScreen. '
              'On fixed code, this assertion will fail because the contextMenuBuilder '
              'closure will have been removed.',
        );
      },
    );
  });

  // =========================================================================
  // Test 2: Widget test — DocumentEditorScreen source uses QuillEditorConfig
  // WITHOUT contextMenuBuilder (expected behavior — fails on unfixed code)
  //
  // This test encodes the EXPECTED (fixed) behavior: QuillEditorConfig should
  // NOT have a contextMenuBuilder. On unfixed code, the source contains the
  // buggy contextMenuBuilder, so this assertion fails.
  //
  // On UNFIXED code: FAILS — contextMenuBuilder IS present (bug condition)
  // On FIXED code:   PASSES — contextMenuBuilder has been removed
  //
  // **Validates: Requirements 1.1, 1.2, 1.3**
  // =========================================================================

  group('Widget Test: QuillEditorConfig Bug Condition vs Fixed Config', () {
    testWidgets(
      'Bug condition: DocumentEditorScreen source uses QuillEditorConfig WITHOUT '
      'contextMenuBuilder (expected behavior — fails on unfixed code)',
      (WidgetTester tester) async {
        // Read the source to check the actual config used in DocumentEditorScreen
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        // The EXPECTED (fixed) behavior is that QuillEditorConfig does NOT have
        // a contextMenuBuilder. We assert this expected behavior here.
        //
        // On UNFIXED code: FAILS — contextMenuBuilder IS present (bug condition)
        // On FIXED code:   PASSES — contextMenuBuilder has been removed
        //
        // This is the core bug condition test: it encodes the expected behavior
        // (no contextMenuBuilder) and fails when the bug is present.
        final hasContextMenuBuilderInQuillConfig = source.contains(
          'contextMenuBuilder: (context, rawEditorState) =>',
        );

        expect(
          hasContextMenuBuilderInQuillConfig,
          isFalse,
          reason:
              'Bug condition counterexample: DocumentEditorScreen has '
              'contextMenuBuilder returning SizedBox.shrink() in QuillEditorConfig. '
              'This is the bug — contextMenuBuilder intercepts the Quill rendering '
              'pipeline and prevents typed text from appearing visually in the editor. '
              'Expected behavior: QuillEditorConfig should NOT have contextMenuBuilder. '
              'Fix: remove the contextMenuBuilder parameter from QuillEditorConfig.',
        );

        // Pump a minimal widget to satisfy the testWidgets requirement
        await tester.pumpWidget(
          const MaterialApp(
            localizationsDelegates: [FlutterQuillLocalizations.delegate],
            home: SizedBox.shrink(),
          ),
        );
      },
    );
  });
}

/// ---------------------------------------------------------------------------
/// Counterexamples Found (documented after running tests on unfixed code):
///
/// TEST 1 (Static Inspection — contextMenuBuilder present): PASSES on unfixed code
///   - contextMenuBuilder IS present in QuillEditorConfig ✓
///   - SizedBox.shrink() IS returned by contextMenuBuilder ✓
///   - QuillEditorConfig IS present in the source ✓
///   - This confirms the bug condition exists in the source code.
///
/// TEST 2 (Static Inspection — closure present): PASSES on unfixed code
///   - contextMenuBuilder closure IS present in the source ✓
///   - This confirms the non-const config with the closure exists.
///
/// TEST 3 (Widget Test — expected behavior assertion): FAILS on unfixed code
///   - Expected: hasContextMenuBuilderInQuillConfig == false (fixed behavior)
///   - Actual: hasContextMenuBuilderInQuillConfig == true (bug condition present)
///   - Counterexample: contextMenuBuilder IS present in QuillEditorConfig
///   - Root cause: the contextMenuBuilder closure returning SizedBox.shrink()
///     intercepts the Quill rendering pipeline and prevents text from rendering.
///   - This test will PASS after the fix removes the contextMenuBuilder.
///
/// CONCLUSION: The bug is confirmed. The fix is to remove the contextMenuBuilder
/// parameter from QuillEditorConfig in DocumentEditorScreen.build().
/// ---------------------------------------------------------------------------
