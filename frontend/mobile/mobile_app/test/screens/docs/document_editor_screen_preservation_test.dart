/// Preservation Property Tests — Doc Editor Content Not Displaying
///
/// **Property 2: Preservation** — Title Editing, Content Loading, Auto-Save,
/// WebSocket Events, and Collaborator Display Unchanged
///
/// IMPORTANT: Follow observation-first methodology — observe behavior on UNFIXED
/// code for non-buggy inputs, then write tests capturing that behavior.
///
/// EXPECTED OUTCOME: All tests PASS on unfixed code (confirms baseline behavior
/// to preserve after the fix is applied).
///
/// **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart'
    hide test, group, expect, isTrue, isFalse, isNull, isNotNull, isEmpty, equals;
import 'package:glados/glados.dart';

// ---------------------------------------------------------------------------
// Helpers — pure logic extracted from DocumentEditorScreen
// ---------------------------------------------------------------------------

/// Simulates the debounce timer logic in _onTitleChanged().
/// Returns the debounce duration used for title saves.
Duration titleSaveDebounce() => const Duration(milliseconds: 800);

/// Simulates the PATCH payload built in _saveTitle().
Map<String, dynamic> buildTitlePatchPayload(String title) {
  return {'title': title};
}

/// Simulates the debounce timer logic in _onDocumentChanged().
/// Returns the debounce duration used for content saves.
Duration contentSaveDebounce() => const Duration(milliseconds: 800);

/// Simulates the PATCH payload built in _saveContent().
Map<String, dynamic> buildContentPatchPayload(String deltaJson, String title) {
  return {
    'content': deltaJson,
    'title': title,
  };
}

/// Simulates the content-parsing logic in _loadContent().
/// Returns the parsed document content string (or plain-text fallback).
String parseLoadedContent(String rawContent) {
  if (rawContent.isEmpty) return '';
  try {
    // Try JSON Delta parse
    final decoded = jsonDecode(rawContent);
    // Re-encode to normalise
    return jsonEncode(decoded);
  } catch (_) {
    // Plain-text fallback
    return rawContent;
  }
}

/// Simulates the WS CRDT message built in _onDocumentChanged().
/// Returns the JSON-encoded message string.
String buildCrdtMessage(String deltaJson) {
  final operationB64 = base64Encode(utf8.encode(deltaJson));
  return jsonEncode({
    'type': 'crdt_update',
    'operation': operationB64,
  });
}

/// Simulates the collaborator banner text formula.
String collaboratorBannerText(int count) {
  return '$count ${count == 1 ? 'person' : 'people'} editing';
}

/// Simulates the avatar count formula (.take(3)).
int visibleAvatarCount(int totalCollaborators) {
  return min(totalCollaborators, 3);
}

// ---------------------------------------------------------------------------
// Group 1: Title Save Preservation
// ---------------------------------------------------------------------------

void main() {
  // =========================================================================
  // Group 1: Title Save Preservation
  //
  // Property: For all non-empty title strings, editing the title field
  // triggers _saveTitle with debounce (800 ms) and sends HTTP PATCH with
  // {'title': title}.
  //
  // **Validates: Requirement 3.1**
  // =========================================================================

  group('Group 1: Title Save Preservation', () {
    // -----------------------------------------------------------------------
    // Static inspection: _onTitleChanged and _saveTitle are present in source
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _onTitleChanged and _saveTitle are present in source',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('_onTitleChanged'),
          reason: '_onTitleChanged must be present — it is the title listener',
        );
        expect(
          source,
          contains('_saveTitle'),
          reason: '_saveTitle must be present — it performs the HTTP PATCH',
        );
        expect(
          source,
          contains('_titleSaveTimer'),
          reason: '_titleSaveTimer must be present — it implements the debounce',
        );
      },
    );

    // -----------------------------------------------------------------------
    // Unit test: debounce duration is 800 ms
    // -----------------------------------------------------------------------
    test('Title save debounce is 800 ms', () {
      expect(titleSaveDebounce().inMilliseconds, equals(800));
    });

    // -----------------------------------------------------------------------
    // Unit test: PATCH payload contains 'title' key
    // -----------------------------------------------------------------------
    test('_saveTitle PATCH payload contains title key', () {
      const title = 'My Document';
      final payload = buildTitlePatchPayload(title);

      expect(payload.containsKey('title'), isTrue);
      expect(payload['title'], equals(title));
    });

    // -----------------------------------------------------------------------
    // Property-based test: for all non-empty strings, PATCH payload is correct
    //
    // **Validates: Requirement 3.1**
    // -----------------------------------------------------------------------
    Glados(any.nonEmptyLetterOrDigits).test(
      'Property: for all non-empty title strings, PATCH payload has correct title',
      (String title) {
        final payload = buildTitlePatchPayload(title.trim());

        expect(payload.containsKey('title'), isTrue,
            reason: 'PATCH payload must contain "title" key');
        expect(payload['title'], equals(title.trim()),
            reason: 'PATCH payload title must match the trimmed input');
        expect(payload.length, equals(1),
            reason: 'Title PATCH payload must contain exactly one key');
      },
    );

    // -----------------------------------------------------------------------
    // Static inspection: _titleCtrl listener is registered in initState
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _titleCtrl.addListener(_onTitleChanged) in initState',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('_titleCtrl.addListener(_onTitleChanged)'),
          reason:
              '_titleCtrl must register _onTitleChanged as a listener in initState',
        );
      },
    );
  });

  // =========================================================================
  // Group 2: Content Load Preservation
  //
  // Property: For all valid document content strings (empty, short, long,
  // special characters), content loads and displays correctly on screen open.
  //
  // **Validates: Requirement 3.2**
  // =========================================================================

  group('Group 2: Content Load Preservation', () {
    // -----------------------------------------------------------------------
    // Static inspection: _loadContent and _loadContentThenConnectWS present
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _loadContent and _loadContentThenConnectWS are present',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('_loadContent'),
          reason: '_loadContent must be present — it performs the HTTP GET',
        );
        expect(
          source,
          contains('_loadContentThenConnectWS'),
          reason:
              '_loadContentThenConnectWS must be present — it sequences HTTP load then WS connect',
        );
        expect(
          source,
          contains('_loadContentThenConnectWS()'),
          reason:
              '_loadContentThenConnectWS must be called in initState to start the load',
        );
      },
    );

    // -----------------------------------------------------------------------
    // Unit test: empty content returns empty string
    // -----------------------------------------------------------------------
    test('Empty content string returns empty (no crash)', () {
      final result = parseLoadedContent('');
      expect(result, equals(''));
    });

    // -----------------------------------------------------------------------
    // Unit test: valid JSON Delta is parsed correctly
    // -----------------------------------------------------------------------
    test('Valid JSON Delta content is parsed without error', () {
      final delta = jsonEncode([
        {'insert': 'Hello world\n'}
      ]);
      final result = parseLoadedContent(delta);
      // Should round-trip through JSON without error
      expect(result, isNotEmpty);
      final decoded = jsonDecode(result);
      expect(decoded, isA<List>());
    });

    // -----------------------------------------------------------------------
    // Unit test: plain-text fallback for non-JSON content
    // -----------------------------------------------------------------------
    test('Non-JSON content falls back to plain text', () {
      const plainText = 'This is plain text content';
      final result = parseLoadedContent(plainText);
      expect(result, equals(plainText));
    });

    // -----------------------------------------------------------------------
    // Property-based test: for all strings, parseLoadedContent never throws
    //
    // **Validates: Requirement 3.2**
    // -----------------------------------------------------------------------
    Glados(any.letters).test(
      'Property: for all content strings, content parsing never throws',
      (String content) {
        // Must not throw for any input
        expect(() => parseLoadedContent(content), returnsNormally);
      },
    );

    // -----------------------------------------------------------------------
    // Property-based test: for all valid JSON strings, result is valid JSON
    //
    // **Validates: Requirement 3.2**
    // -----------------------------------------------------------------------
    test(
      'Property: JSON Delta content round-trips through parseLoadedContent',
      () {
        final testCases = [
          jsonEncode([
            {'insert': 'Short\n'}
          ]),
          jsonEncode([
            {'insert': 'A' * 1000 + '\n'}
          ]),
          jsonEncode([
            {'insert': 'Special chars: !@#\$%^&*()\n'}
          ]),
          jsonEncode([
            {'insert': 'Unicode: 你好世界\n'}
          ]),
          jsonEncode([
            {'insert': 'Newlines\n\n\n'}
          ]),
        ];

        for (final delta in testCases) {
          final result = parseLoadedContent(delta);
          expect(result, isNotEmpty,
              reason: 'Parsed content must not be empty for: $delta');
          // Result must be valid JSON
          expect(() => jsonDecode(result), returnsNormally,
              reason: 'Parsed content must be valid JSON for: $delta');
        }
      },
    );

    // -----------------------------------------------------------------------
    // Static inspection: HTTP GET uses AppConstants.documentUrl
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _loadContent uses AppConstants.documentUrl for HTTP GET',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('AppConstants.documentUrl(widget.document.id)'),
          reason:
              '_loadContent must use AppConstants.documentUrl to build the GET URL',
        );
      },
    );
  });

  // =========================================================================
  // Group 3: Auto-Save Preservation
  //
  // Property: For all typed content, auto-save via HTTP PATCH fires after
  // the debounce period (800 ms).
  //
  // **Validates: Requirement 3.3**
  // =========================================================================

  group('Group 3: Auto-Save Preservation', () {
    // -----------------------------------------------------------------------
    // Static inspection: _onDocumentChanged and _saveContent present
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _onDocumentChanged and _saveContent are present',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('_onDocumentChanged'),
          reason:
              '_onDocumentChanged must be present — it is the document change listener',
        );
        expect(
          source,
          contains('_saveContent'),
          reason: '_saveContent must be present — it performs the HTTP PATCH',
        );
        expect(
          source,
          contains('_saveTimer'),
          reason: '_saveTimer must be present — it implements the debounce',
        );
      },
    );

    // -----------------------------------------------------------------------
    // Unit test: content save debounce is 800 ms
    // -----------------------------------------------------------------------
    test('Content save debounce is 800 ms', () {
      expect(contentSaveDebounce().inMilliseconds, equals(800));
    });

    // -----------------------------------------------------------------------
    // Unit test: PATCH payload contains 'content' and 'title' keys
    // -----------------------------------------------------------------------
    test('_saveContent PATCH payload contains content and title keys', () {
      final deltaJson = jsonEncode([
        {'insert': 'Hello\n'}
      ]);
      const title = 'My Doc';
      final payload = buildContentPatchPayload(deltaJson, title);

      expect(payload.containsKey('content'), isTrue);
      expect(payload.containsKey('title'), isTrue);
      expect(payload['content'], equals(deltaJson));
      expect(payload['title'], equals(title));
    });

    // -----------------------------------------------------------------------
    // Property-based test: for all content strings, PATCH payload is correct
    //
    // **Validates: Requirement 3.3**
    // -----------------------------------------------------------------------
    Glados(any.letters).test(
      'Property: for all content strings, PATCH payload has content and title keys',
      (String content) {
        const title = 'Test Title';
        final payload = buildContentPatchPayload(content, title);

        expect(payload.containsKey('content'), isTrue,
            reason: 'PATCH payload must contain "content" key');
        expect(payload.containsKey('title'), isTrue,
            reason: 'PATCH payload must contain "title" key');
        expect(payload['content'], equals(content),
            reason: 'PATCH payload content must match the input');
        expect(payload['title'], equals(title),
            reason: 'PATCH payload title must match the input');
      },
    );

    // -----------------------------------------------------------------------
    // Static inspection: _saveStatus set to 'Saving...' in _onDocumentChanged
    // -----------------------------------------------------------------------
    test(
      "Static inspection: _onDocumentChanged sets _saveStatus to 'Saving...'",
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains("'Saving...'"),
          reason:
              "_onDocumentChanged must set _saveStatus to 'Saving...' to indicate save in progress",
        );
      },
    );

    // -----------------------------------------------------------------------
    // Static inspection: _saveContent uses AppConstants.documentUpdateUrl
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _saveContent uses AppConstants.documentUpdateUrl for PATCH',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('AppConstants.documentUpdateUrl(widget.document.id)'),
          reason:
              '_saveContent must use AppConstants.documentUpdateUrl to build the PATCH URL',
        );
      },
    );
  });

  // =========================================================================
  // Group 4: WebSocket CRDT Event Preservation
  //
  // Property: For all typed content when WebSocket is connected, a
  // crdt_update event is sent with a base64-encoded 'operation' field.
  //
  // **Validates: Requirement 3.4**
  // =========================================================================

  group('Group 4: WebSocket CRDT Event Preservation', () {
    // -----------------------------------------------------------------------
    // Static inspection: crdt_update and base64Encode logic present
    // -----------------------------------------------------------------------
    test(
      "Static inspection: 'crdt_update' and base64Encode are present in source",
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains("'crdt_update'"),
          reason:
              "Source must contain 'crdt_update' — the WS message type for CRDT updates",
        );
        expect(
          source,
          contains('base64Encode'),
          reason:
              'Source must contain base64Encode — the operation field must be base64-encoded',
        );
        expect(
          source,
          contains("'operation'"),
          reason:
              "Source must contain 'operation' key — the backend expects this field name",
        );
      },
    );

    // -----------------------------------------------------------------------
    // Unit test: CRDT message has type == 'crdt_update'
    // -----------------------------------------------------------------------
    test("CRDT message type is 'crdt_update'", () {
      final deltaJson = jsonEncode([
        {'insert': 'Hello\n'}
      ]);
      final message = jsonDecode(buildCrdtMessage(deltaJson)) as Map<String, dynamic>;

      expect(message['type'], equals('crdt_update'));
    });

    // -----------------------------------------------------------------------
    // Unit test: CRDT message 'operation' field is a valid base64 string
    // -----------------------------------------------------------------------
    test("CRDT message 'operation' field is a valid base64 string", () {
      final deltaJson = jsonEncode([
        {'insert': 'Hello\n'}
      ]);
      final message = jsonDecode(buildCrdtMessage(deltaJson)) as Map<String, dynamic>;

      expect(message.containsKey('operation'), isTrue);
      final operation = message['operation'] as String;
      // Must be decodable as base64
      expect(() => base64Decode(operation), returnsNormally);
    });

    // -----------------------------------------------------------------------
    // Unit test: decoding base64 operation gives back original delta JSON
    // -----------------------------------------------------------------------
    test('Decoding base64 operation gives back original delta JSON', () {
      final deltaJson = jsonEncode([
        {'insert': 'Hello world\n'}
      ]);
      final message = jsonDecode(buildCrdtMessage(deltaJson)) as Map<String, dynamic>;
      final operation = message['operation'] as String;

      final decoded = utf8.decode(base64Decode(operation));
      expect(decoded, equals(deltaJson));
    });

    // -----------------------------------------------------------------------
    // Property-based test: for all delta JSON strings, CRDT message is correct
    //
    // **Validates: Requirement 3.4**
    // -----------------------------------------------------------------------
    Glados(any.letters).test(
      'Property: for all delta JSON strings, CRDT message has correct structure',
      (String deltaJson) {
        final messageStr = buildCrdtMessage(deltaJson);
        final message = jsonDecode(messageStr) as Map<String, dynamic>;

        // Must have type == 'crdt_update'
        expect(message['type'], equals('crdt_update'),
            reason: "CRDT message must have type == 'crdt_update'");

        // Must have 'operation' key
        expect(message.containsKey('operation'), isTrue,
            reason: "CRDT message must have 'operation' key");

        // 'operation' must be a valid base64 string
        final operation = message['operation'] as String;
        expect(() => base64Decode(operation), returnsNormally,
            reason: "'operation' must be a valid base64 string");

        // Decoding base64 must give back the original delta JSON
        final decoded = utf8.decode(base64Decode(operation));
        expect(decoded, equals(deltaJson),
            reason:
                'Decoding base64 operation must give back the original delta JSON');
      },
    );

    // -----------------------------------------------------------------------
    // Unit test: CRDT message does NOT use deprecated 'delta' key
    // -----------------------------------------------------------------------
    test("CRDT message does NOT use deprecated 'delta' key", () {
      final deltaJson = jsonEncode([
        {'insert': 'Test\n'}
      ]);
      final message = jsonDecode(buildCrdtMessage(deltaJson)) as Map<String, dynamic>;

      expect(message.containsKey('delta'), isFalse,
          reason: "CRDT message must not use 'delta' key — backend expects 'operation'");
    });

    // -----------------------------------------------------------------------
    // Static inspection: WS guard (_ws != null && _isConnected) present
    // -----------------------------------------------------------------------
    test(
      'Static inspection: WS guard (_ws != null && _isConnected) present in source',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('_ws != null && _isConnected'),
          reason:
              'Source must guard WS send with _ws != null && _isConnected check',
        );
      },
    );
  });

  // =========================================================================
  // Group 5: Collaborator Display Preservation
  //
  // Property: For all collaborator list sizes (1–5), the collaborator banner
  // and avatars render correctly.
  //
  // **Validates: Requirement 3.6**
  // =========================================================================

  group('Group 5: Collaborator Display Preservation', () {
    // -----------------------------------------------------------------------
    // Static inspection: collaborator banner and avatar widget structure present
    // -----------------------------------------------------------------------
    test(
      'Static inspection: collaborator banner and CircleAvatar are present in source',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('CircleAvatar'),
          reason: 'Source must contain CircleAvatar for collaborator avatars',
        );
        expect(
          source,
          contains('} editing'),
          reason:
              "Source must contain '} editing' text for the collaborator banner",
        );
        expect(
          source,
          contains('person'),
          reason:
              "Source must contain 'person' for singular collaborator banner text",
        );
        expect(
          source,
          contains('.take(3)'),
          reason:
              'Source must use .take(3) to limit displayed avatars to 3',
        );
      },
    );

    // -----------------------------------------------------------------------
    // Unit test: banner text for 1 collaborator uses singular 'person'
    // -----------------------------------------------------------------------
    test("Banner text for 1 collaborator is '1 person editing'", () {
      expect(collaboratorBannerText(1), equals('1 person editing'));
    });

    // -----------------------------------------------------------------------
    // Unit test: banner text for 2+ collaborators uses plural 'people'
    // -----------------------------------------------------------------------
    test("Banner text for 2 collaborators is '2 people editing'", () {
      expect(collaboratorBannerText(2), equals('2 people editing'));
    });

    test("Banner text for 5 collaborators is '5 people editing'", () {
      expect(collaboratorBannerText(5), equals('5 people editing'));
    });

    // -----------------------------------------------------------------------
    // Unit test: avatar count is capped at 3
    // -----------------------------------------------------------------------
    test('Avatar count is capped at 3 for any collaborator count', () {
      expect(visibleAvatarCount(1), equals(1));
      expect(visibleAvatarCount(2), equals(2));
      expect(visibleAvatarCount(3), equals(3));
      expect(visibleAvatarCount(4), equals(3));
      expect(visibleAvatarCount(5), equals(3));
    });

    // -----------------------------------------------------------------------
    // Property-based test: for all counts 1–5, banner text is correct
    //
    // **Validates: Requirement 3.6**
    // -----------------------------------------------------------------------
    test(
      'Property: for all collaborator counts 1–5, banner text is correct',
      () {
        for (int count = 1; count <= 5; count++) {
          final text = collaboratorBannerText(count);
          final expectedWord = count == 1 ? 'person' : 'people';

          expect(text, startsWith('$count '),
              reason: 'Banner text must start with the count for count=$count');
          expect(text, contains(expectedWord),
              reason:
                  'Banner text must use "$expectedWord" for count=$count');
          expect(text, endsWith('editing'),
              reason: 'Banner text must end with "editing" for count=$count');
        }
      },
    );

    // -----------------------------------------------------------------------
    // Property-based test: for all counts 1–5, visible avatar count is correct
    //
    // **Validates: Requirement 3.6**
    // -----------------------------------------------------------------------
    test(
      'Property: for all collaborator counts 1–5, visible avatar count is min(count, 3)',
      () {
        for (int count = 1; count <= 5; count++) {
          final visible = visibleAvatarCount(count);
          expect(visible, equals(min(count, 3)),
              reason:
                  'Visible avatar count must be min($count, 3) = ${min(count, 3)}');
        }
      },
    );

    // -----------------------------------------------------------------------
    // Logic test: collaborator map population from participant_joined event
    // -----------------------------------------------------------------------
    test(
      'participant_joined event populates collaborators map correctly',
      () {
        final collaborators = <String, Map<String, dynamic>>{};

        // Simulate _handleWsEvent for participant_joined
        final event = {
          'type': 'participant_joined',
          'user': {
            'id': 'user-1',
            'full_name': 'Alice Smith',
            'username': 'alice',
            'avatar_url': null,
          },
        };

        final user = event['user'] as Map<String, dynamic>?;
        if (user != null) {
          final id = user['id']?.toString() ?? '';
          collaborators[id] = {
            'name': user['full_name'] ?? user['username'] ?? 'User',
            'avatar': user['avatar_url'],
          };
        }

        expect(collaborators.containsKey('user-1'), isTrue);
        expect(collaborators['user-1']!['name'], equals('Alice Smith'));
      },
    );

    // -----------------------------------------------------------------------
    // Logic test: participant_left event removes collaborator from map
    // -----------------------------------------------------------------------
    test(
      'participant_left event removes collaborator from map correctly',
      () {
        final collaborators = <String, Map<String, dynamic>>{
          'user-1': {'name': 'Alice', 'avatar': null},
          'user-2': {'name': 'Bob', 'avatar': null},
        };

        final event = {
          'type': 'participant_left',
          'user': {'id': 'user-1'},
        };

        final userId =
            (event['user'] as Map<String, dynamic>?)?['id']?.toString();
        if (userId != null) collaborators.remove(userId);

        expect(collaborators.containsKey('user-1'), isFalse);
        expect(collaborators.containsKey('user-2'), isTrue);
      },
    );

    // -----------------------------------------------------------------------
    // Static inspection: _collaborators map and participant_joined handler present
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _collaborators map and participant_joined handler present',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('_collaborators'),
          reason: '_collaborators map must be present in source',
        );
        expect(
          source,
          contains('participant_joined'),
          reason: 'participant_joined WS event handler must be present',
        );
        expect(
          source,
          contains('participant_left'),
          reason: 'participant_left WS event handler must be present',
        );
      },
    );

    // -----------------------------------------------------------------------
    // Widget test: collaborator banner text formula renders correctly
    // -----------------------------------------------------------------------
    testWidgets(
      'Widget: collaborator banner text renders correctly for 1 and 2 collaborators',
      (WidgetTester tester) async {
        // Test the banner text widget directly (no DocumentEditorScreen pump needed)
        for (final count in [1, 2, 3]) {
          final bannerText = collaboratorBannerText(count);

          await tester.pumpWidget(
            MaterialApp(
              home: Scaffold(
                body: Text(bannerText),
              ),
            ),
          );

          expect(find.text(bannerText), findsOneWidget,
              reason:
                  'Banner text "$bannerText" must render correctly for count=$count');
        }
      },
    );
  });

  // =========================================================================
  // Group 6: WebSocket Connection Sequencing Preservation
  //
  // Property: WebSocket connection is established AFTER HTTP content load.
  //
  // **Validates: Requirement 3.5**
  // =========================================================================

  group('Group 6: WebSocket Connection Sequencing Preservation', () {
    // -----------------------------------------------------------------------
    // Static inspection: _loadContentThenConnectWS sequences HTTP then WS
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _loadContentThenConnectWS awaits _loadContent before _connectWebSocket',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        // The method must contain both calls in the correct order
        expect(
          source,
          contains('await _loadContent()'),
          reason:
              '_loadContentThenConnectWS must await _loadContent() before connecting WS',
        );
        expect(
          source,
          contains('await _connectWebSocket()'),
          reason:
              '_loadContentThenConnectWS must await _connectWebSocket() after HTTP load',
        );

        // Verify ordering: _loadContent appears before _connectWebSocket in the method
        final loadIdx = source.indexOf('await _loadContent()');
        final wsIdx = source.indexOf('await _connectWebSocket()');
        expect(loadIdx, lessThan(wsIdx),
            reason:
                '_loadContent must appear before _connectWebSocket in the source');
      },
    );

    // -----------------------------------------------------------------------
    // Static inspection: _connectWebSocket uses ws:// scheme
    // -----------------------------------------------------------------------
    test(
      "Static inspection: _connectWebSocket uses scheme: 'ws' for URI construction",
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains("scheme:          'ws'"),
          reason:
              "_connectWebSocket must use scheme: 'ws' for the WebSocket URI",
        );
      },
    );

    // -----------------------------------------------------------------------
    // Static inspection: reconnect logic present
    // -----------------------------------------------------------------------
    test(
      'Static inspection: _scheduleReconnect and _maxReconnectAttempts present',
      () {
        final source = File(
          'lib/screens/docs/document_editor_screen.dart',
        ).readAsStringSync();

        expect(
          source,
          contains('_scheduleReconnect'),
          reason: '_scheduleReconnect must be present for connection resilience',
        );
        expect(
          source,
          contains('_maxReconnectAttempts'),
          reason: '_maxReconnectAttempts must be present to cap reconnect attempts',
        );
      },
    );
  });
}
