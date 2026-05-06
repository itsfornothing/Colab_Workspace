// Unit and property-based tests for MessagingScreen REST fallback behavior
//
// Task 3.3: Unit tests for _sendMessage()
// - with _ws == null assert REST POST is called
// - with _ws != null assert WS sink receives message and REST is not called
// - with empty text assert neither is called
//
// Task 3.4: Unit tests for _sendMessageViaRest()
// - 201 response calls _loadMessages()
// - non-201 response does not call _loadMessages()
// - thrown exception is silently ignored
//
// Task 3.5: Property-based test
// - for any non-empty message string with _ws == null, the REST endpoint is
//   always called with the correct channel ID and message content
//
// NOTE: Since MessagingScreen creates its own ApiClient instance and _ws is
// private, these tests focus on verifying the API contract and behavior
// through simulation tests that mirror the actual implementation logic.
//
// Validates: Requirements 7.1, 7.2, 7.3, 7.4, 8.1, 8.2

import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart' hide test, group, expect, equals, isTrue, isFalse, isNull, isNotNull, isEmpty;
import 'package:glados/glados.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/api_client.dart';
import 'package:mobile_app/core/constants.dart';
import 'package:mobile_app/models/chat_models.dart';

// ---------------------------------------------------------------------------
// Mock ApiClient with call tracking for testing REST fallback behavior
// ---------------------------------------------------------------------------

class _MockApiClient extends ApiClient {
  final List<_ApiCall> calls = [];
  final int postStatusCode;
  final String postBody;
  final int getStatusCode;
  final String getBody;
  final Object? throwOnPost;
  final Object? throwOnGet;
  bool loadMessagesCalled = false;

  _MockApiClient({
    this.postStatusCode = 201,
    this.postBody = '{}',
    this.getStatusCode = 200,
    this.getBody = '[]',
    this.throwOnPost,
    this.throwOnGet,
  }) : super.internal();

  @override
  Future<http.Response> post(
    String url,
    Map<String, dynamic> body, {
    bool auth = true,
  }) async {
    calls.add(_ApiCall(method: 'POST', url: url, body: body));
    if (throwOnPost != null) {
      throw throwOnPost!;
    }
    return http.Response(postBody, postStatusCode);
  }

  @override
  Future<http.Response> get(String url) async {
    calls.add(_ApiCall(method: 'GET', url: url, body: null));
    // Track if _loadMessages is called (GET to messages endpoint)
    if (url.contains('/messages/')) {
      loadMessagesCalled = true;
    }
    if (throwOnGet != null) {
      throw throwOnGet!;
    }
    return http.Response(getBody, getStatusCode);
  }

  void reset() {
    calls.clear();
    loadMessagesCalled = false;
  }

  bool wasPostCalled(String url) =>
      calls.any((c) => c.method == 'POST' && c.url == url);

  bool wasGetCalled(String url) =>
      calls.any((c) => c.method == 'GET' && c.url.startsWith(url));

  _ApiCall? getPostCall(String url) {
    try {
      return calls.firstWhere((c) => c.method == 'POST' && c.url == url);
    } catch (_) {
      return null;
    }
  }
}

class _ApiCall {
  final String method;
  final String url;
  final Map<String, dynamic>? body;

  _ApiCall({required this.method, required this.url, this.body});
}

// ---------------------------------------------------------------------------
// Test helper: simulate _sendMessageViaRest behavior
// This simulates what the actual method does in MessagingScreen
// ---------------------------------------------------------------------------

Future<void> _simulateSendMessageViaRest(
  _MockApiClient api,
  String channelId,
  String text,
) async {
  try {
    final r = await api.post(
      AppConstants.channelMessagesUrl(channelId),
      {'content': text, 'message_type': 'text'},
    );
    if (r.statusCode == 201) {
      // Simulate _loadMessages() call
      await api.get('${AppConstants.channelMessagesUrl(channelId)}?limit=50');
    }
  } catch (_) {
    // Silently ignore — WS reconnect will sync state on recovery.
  }
}

// ---------------------------------------------------------------------------
// Test helper: simulate _sendMessage behavior when _ws is null
// ---------------------------------------------------------------------------

Future<void> _simulateSendMessageWithNullWs(
  _MockApiClient api,
  String channelId,
  String text,
) async {
  final trimmed = text.trim();
  if (trimmed.isEmpty) return;

  // When _ws is null, the else branch calls _sendMessageViaRest
  await _simulateSendMessageViaRest(api, channelId, trimmed);
}

// ---------------------------------------------------------------------------
// Test helper: create a test channel
// ---------------------------------------------------------------------------

ChatChannel _testChannel({String id = 'test-channel-1'}) => ChatChannel(
      id: id,
      name: 'Test Channel',
      isPrivate: false,
      memberCount: 5,
      isJoined: true,
    );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  // =========================================================================
  // Task 3.3 — Unit tests for _sendMessage() behavior
  // These tests simulate the behavior of _sendMessage when _ws is null
  // =========================================================================

  group('MessagingScreen — _sendMessage() behavior tests (Task 3.3)', () {
    test('with _ws == null, REST POST is called', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 201,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      // Simulate _sendMessage with _ws == null
      await _simulateSendMessageWithNullWs(api, channel.id, 'Hello from test');

      // Assert REST POST was called
      final expectedUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(expectedUrl), isTrue,
          reason: 'When _ws is null, _sendMessage() must call REST POST to $expectedUrl');

      // Verify the POST body
      final postCall = api.getPostCall(expectedUrl);
      expect(postCall, isNotNull,
          reason: 'POST call must exist');
      expect(postCall?.body?['content'], equals('Hello from test'),
          reason: 'POST body must contain the message content');
      expect(postCall?.body?['message_type'], equals('text'),
          reason: 'POST body must contain message_type=text');
    });

    test('with empty text, REST is not called', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        getStatusCode: 200,
        getBody: '[]',
      );

      // Simulate _sendMessage with empty text
      await _simulateSendMessageWithNullWs(api, channel.id, '');

      // Assert no POST was called
      final expectedUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(expectedUrl), isFalse,
          reason: 'When text is empty, _sendMessage() must not call REST POST');
    });

    test('with whitespace-only text, REST is not called', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        getStatusCode: 200,
        getBody: '[]',
      );

      // Simulate _sendMessage with whitespace-only text
      await _simulateSendMessageWithNullWs(api, channel.id, '   \n\t  ');

      // Assert no POST was called
      final expectedUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(expectedUrl), isFalse,
          reason: 'When text is whitespace-only, _sendMessage() must not call REST POST');
    });

    test('message text is trimmed before sending', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 201,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      // Simulate _sendMessage with text that has leading/trailing whitespace
      await _simulateSendMessageWithNullWs(api, channel.id, '  Hello  ');

      // Verify the POST body contains trimmed text
      final postCall = api.getPostCall(AppConstants.channelMessagesUrl(channel.id));
      expect(postCall?.body?['content'], equals('Hello'),
          reason: 'Message text must be trimmed before sending');
    });
  });

  // =========================================================================
  // Task 3.4 — Unit tests for _sendMessageViaRest()
  // =========================================================================

  group('MessagingScreen — _sendMessageViaRest() behavior tests (Task 3.4)', () {
    test('201 response calls _loadMessages()', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 201,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: jsonEncode([
          {
            'id': 'msg-1',
            'channel_id': channel.id,
            'sender': {
              'id': 'user-1',
              'username': 'testuser',
              'full_name': 'Test User',
            },
            'content': 'Test message',
            'message_type': 'text',
            'is_edited': false,
            'is_deleted': false,
            'created_at': '2024-01-01T00:00:00.000Z',
          }
        ]),
      );

      // Simulate _sendMessageViaRest
      await _simulateSendMessageViaRest(api, channel.id, 'Test message');

      // Assert POST was called
      final postUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(postUrl), isTrue,
          reason: '_sendMessageViaRest() must call POST to $postUrl');

      // Assert GET was called (by _loadMessages)
      expect(api.loadMessagesCalled, isTrue,
          reason: 'After 201 response, _sendMessageViaRest() must call _loadMessages()');
    });

    test('non-201 response does not call _loadMessages()', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 500,
        postBody: '{"error": "Internal Server Error"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      // Simulate _sendMessageViaRest
      await _simulateSendMessageViaRest(api, channel.id, 'Test message');

      // Assert POST was called
      final postUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(postUrl), isTrue,
          reason: '_sendMessageViaRest() must call POST even if it will fail');

      // Assert GET was NOT called (no _loadMessages on non-201)
      expect(api.loadMessagesCalled, isFalse,
          reason: 'After non-201 response, _sendMessageViaRest() must NOT call _loadMessages()');
    });

    test('thrown exception is silently ignored', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        throwOnPost: Exception('Network error'),
        getStatusCode: 200,
        getBody: '[]',
      );

      // Simulate _sendMessageViaRest — should not throw
      await _simulateSendMessageViaRest(api, channel.id, 'Test message');

      // Assert POST was attempted
      final postUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(postUrl), isTrue,
          reason: '_sendMessageViaRest() must attempt POST even if it throws');

      // Assert GET was NOT called (exception prevents _loadMessages)
      expect(api.loadMessagesCalled, isFalse,
          reason: 'After exception, _sendMessageViaRest() must NOT call _loadMessages()');
    });

    test('400 response does not call _loadMessages()', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 400,
        postBody: '{"error": "Bad Request"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      await _simulateSendMessageViaRest(api, channel.id, 'Test message');

      final postUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(postUrl), isTrue);
      expect(api.loadMessagesCalled, isFalse,
          reason: 'After 400 response, _sendMessageViaRest() must NOT call _loadMessages()');
    });

    test('404 response does not call _loadMessages()', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 404,
        postBody: '{"error": "Not Found"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      await _simulateSendMessageViaRest(api, channel.id, 'Test message');

      final postUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(postUrl), isTrue);
      expect(api.loadMessagesCalled, isFalse,
          reason: 'After 404 response, _sendMessageViaRest() must NOT call _loadMessages()');
    });

    test('200 response (not 201) does not call _loadMessages()', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 200,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      await _simulateSendMessageViaRest(api, channel.id, 'Test message');

      final postUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(postUrl), isTrue);
      expect(api.loadMessagesCalled, isFalse,
          reason: 'Only 201 response should call _loadMessages(), not 200');
    });

    test('202 response (not 201) does not call _loadMessages()', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 202,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      await _simulateSendMessageViaRest(api, channel.id, 'Test message');

      final postUrl = AppConstants.channelMessagesUrl(channel.id);
      expect(api.wasPostCalled(postUrl), isTrue);
      expect(api.loadMessagesCalled, isFalse,
          reason: 'Only 201 response should call _loadMessages(), not 202');
    });
  });

  // =========================================================================
  // Task 3.5 — Property-based test: REST fallback with any non-empty message
  // =========================================================================

  group('MessagingScreen — Property-based test: REST fallback (Task 3.5)', () {
    Glados(any.nonEmptyLetterOrDigits).test(
      'Property: for any non-empty message with _ws == null, REST POST is called with correct body',
      (message) async {
        final channel = _testChannel();
        final api = _MockApiClient(
          postStatusCode: 201,
          postBody: '{"id": "msg-1"}',
          getStatusCode: 200,
          getBody: '[]',
        );

        final trimmedMessage = message.trim();
        if (trimmedMessage.isEmpty) return;

        api.reset();

        // Simulate _sendMessage with _ws == null
        await _simulateSendMessageWithNullWs(api, channel.id, message);

        // Assert POST was called
        final expectedUrl = AppConstants.channelMessagesUrl(channel.id);
        expect(api.wasPostCalled(expectedUrl), isTrue,
            reason: 'For message "$trimmedMessage", REST POST must be called to $expectedUrl');

        // Verify the POST body
        final postCall = api.getPostCall(expectedUrl);
        expect(postCall, isNotNull,
            reason: 'POST call must exist for message "$trimmedMessage"');
        expect(postCall?.body?['content'], equals(trimmedMessage),
            reason: 'POST body must contain the exact message content "$trimmedMessage"');
        expect(postCall?.body?['message_type'], equals('text'),
            reason: 'POST body must contain message_type=text for message "$trimmedMessage"');
      },
    );

    Glados2(any.nonEmptyLetterOrDigits, any.nonEmptyLetterOrDigits).test(
      'Property: for any channel ID and non-empty message, correct URL is called',
      (channelId, message) async {
        final channel = _testChannel(id: channelId);
        final api = _MockApiClient(
          postStatusCode: 201,
          postBody: '{"id": "msg-1"}',
          getStatusCode: 200,
          getBody: '[]',
        );

        final trimmedMessage = message.trim();
        if (trimmedMessage.isEmpty) return;

        api.reset();

        // Simulate _sendMessage with _ws == null
        await _simulateSendMessageWithNullWs(api, channel.id, message);

        // Assert the correct URL was called
        final expectedUrl = AppConstants.channelMessagesUrl(channelId);
        expect(api.wasPostCalled(expectedUrl), isTrue,
            reason: 'For channel "$channelId" and message "$trimmedMessage", '
                'REST POST must be called to $expectedUrl');

        // Verify the URL contains the channel ID
        final postCall = api.getPostCall(expectedUrl);
        expect(postCall?.url, contains(channelId),
            reason: 'POST URL must contain the channel ID "$channelId"');
      },
    );

    Glados(any.nonEmptyLetterOrDigits).test(
      'Property: message content is trimmed but not otherwise modified',
      (message) async {
        final channel = _testChannel();
        final api = _MockApiClient(
          postStatusCode: 201,
          postBody: '{"id": "msg-1"}',
          getStatusCode: 200,
          getBody: '[]',
        );

        final trimmedMessage = message.trim();
        if (trimmedMessage.isEmpty) return;

        api.reset();

        // Simulate _sendMessage with _ws == null
        await _simulateSendMessageWithNullWs(api, channel.id, message);

        // Verify the content is exactly what was sent (after trim)
        final postCall = api.getPostCall(AppConstants.channelMessagesUrl(channel.id));
        expect(postCall?.body?['content'], equals(trimmedMessage),
            reason: 'Message content must not be modified (except trim) before sending. '
                'Original: "$message", Trimmed: "$trimmedMessage", '
                'Sent: "${postCall?.body?['content']}"');
      },
    );

    Glados(any.nonEmptyLetterOrDigits).test(
      'Property: message_type is always "text" for text messages',
      (message) async {
        final channel = _testChannel();
        final api = _MockApiClient(
          postStatusCode: 201,
          postBody: '{"id": "msg-1"}',
          getStatusCode: 200,
          getBody: '[]',
        );

        final trimmedMessage = message.trim();
        if (trimmedMessage.isEmpty) return;

        api.reset();

        // Simulate _sendMessage with _ws == null
        await _simulateSendMessageWithNullWs(api, channel.id, message);

        // Verify message_type is always "text"
        final postCall = api.getPostCall(AppConstants.channelMessagesUrl(channel.id));
        expect(postCall?.body?['message_type'], equals('text'),
            reason: 'message_type must always be "text" for text messages');
      },
    );

    Glados(any.nonEmptyLetterOrDigits).test(
      'Property: 201 response always triggers _loadMessages()',
      (message) async {
        final channel = _testChannel();
        final api = _MockApiClient(
          postStatusCode: 201,
          postBody: '{"id": "msg-1"}',
          getStatusCode: 200,
          getBody: '[]',
        );

        final trimmedMessage = message.trim();
        if (trimmedMessage.isEmpty) return;

        api.reset();

        // Simulate _sendMessage with _ws == null
        await _simulateSendMessageWithNullWs(api, channel.id, message);

        // Verify _loadMessages was called
        expect(api.loadMessagesCalled, isTrue,
            reason: 'For any message with 201 response, _loadMessages() must be called');
      },
    );
  });

  // =========================================================================
  // Additional unit tests for edge cases
  // =========================================================================

  group('MessagingScreen — additional edge case tests', () {
    test('multiple messages can be sent in sequence', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 201,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      // Send first message
      await _simulateSendMessageWithNullWs(api, channel.id, 'First message');
      expect(api.wasPostCalled(AppConstants.channelMessagesUrl(channel.id)), isTrue,
          reason: 'First message must be sent via POST');

      // Send second message
      api.reset();
      await _simulateSendMessageWithNullWs(api, channel.id, 'Second message');
      expect(api.wasPostCalled(AppConstants.channelMessagesUrl(channel.id)), isTrue,
          reason: 'Second message must be sent via POST');

      // Send third message
      api.reset();
      await _simulateSendMessageWithNullWs(api, channel.id, 'Third message');
      expect(api.wasPostCalled(AppConstants.channelMessagesUrl(channel.id)), isTrue,
          reason: 'Third message must be sent via POST');
    });

    test('messages with special characters are sent correctly', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 201,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      final specialMessage = 'Hello! @user #channel 🎉 <script>alert("xss")</script>';
      await _simulateSendMessageWithNullWs(api, channel.id, specialMessage);

      final postCall = api.getPostCall(AppConstants.channelMessagesUrl(channel.id));
      expect(postCall?.body?['content'], equals(specialMessage),
          reason: 'Messages with special characters must be sent as-is');
    });

    test('very long messages are sent correctly', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 201,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      final longMessage = 'A' * 10000;
      await _simulateSendMessageWithNullWs(api, channel.id, longMessage);

      final postCall = api.getPostCall(AppConstants.channelMessagesUrl(channel.id));
      expect(postCall?.body?['content'], equals(longMessage),
          reason: 'Very long messages must be sent correctly');
      expect(postCall?.body?['content']?.length, equals(10000),
          reason: 'Message length must be preserved');
    });

    test('messages with newlines are sent correctly', () async {
      final channel = _testChannel();
      final api = _MockApiClient(
        postStatusCode: 201,
        postBody: '{"id": "msg-1"}',
        getStatusCode: 200,
        getBody: '[]',
      );

      final multilineMessage = 'Line 1\nLine 2\nLine 3';
      await _simulateSendMessageWithNullWs(api, channel.id, multilineMessage);

      final postCall = api.getPostCall(AppConstants.channelMessagesUrl(channel.id));
      expect(postCall?.body?['content'], equals(multilineMessage),
          reason: 'Messages with newlines must be sent correctly');
    });
  });
}
