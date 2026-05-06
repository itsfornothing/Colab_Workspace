// Basic smoke test for the CollabApp widget.
//
// This test verifies that the app can be built and rendered without throwing
// an exception. It replaces the default Flutter template test which referenced
// a non-existent MyApp constructor.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile_app/main.dart';

void main() {
  testWidgets('CollabApp smoke test — app builds without throwing',
      (WidgetTester tester) async {
    // Build the app inside a ProviderScope (required by Riverpod).
    await tester.pumpWidget(
      const ProviderScope(child: CollabApp()),
    );

    // Allow the first frame to render (auth check starts in initState).
    await tester.pump();

    // The app should render without throwing. The _AuthGate shows a loading
    // spinner while checking stored credentials, so we just verify the
    // Scaffold is present.
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
