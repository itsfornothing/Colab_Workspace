import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../core/token_storage.dart';

class VideoCallScreen extends StatefulWidget {
  final String roomId;

  const VideoCallScreen({super.key, required this.roomId});

  @override
  State<VideoCallScreen> createState() => _VideoCallScreenState();
}

class _VideoCallScreenState extends State<VideoCallScreen> {
  final _storage = TokenStorage();
  WebSocketChannel? _ws;

  final _localRenderer = RTCVideoRenderer();
  final Map<String, RTCVideoRenderer> _remoteRenderers = {};
  final Map<String, RTCPeerConnection> _peerConnections = {};

  MediaStream? _localStream;
  bool _isMuted = false;
  bool _isCameraOff = false;
  bool _showParticipants = false;
  List<Map<String, dynamic>> _participants = [];

  @override
  void initState() {
    super.initState();
    _initRenderers();
    _connectWebSocket();
  }

  @override
  void dispose() {
    _localRenderer.dispose();
    for (final r in _remoteRenderers.values) {
      r.dispose();
    }
    for (final pc in _peerConnections.values) {
      pc.close();
    }
    _localStream?.dispose();
    _ws?.sink.close();
    super.dispose();
  }

  Future<void> _initRenderers() async {
    await _localRenderer.initialize();
    try {
      _localStream = await navigator.mediaDevices.getUserMedia({
        'audio': true,
        'video': {'facingMode': 'user'},
      });
      _localRenderer.srcObject = _localStream;
      if (mounted) setState(() {});
    } catch (e) {
      debugPrint('Error getting media: $e');
      // Show a non-fatal message rather than crashing — the user can still
      // participate in audio-only mode or grant permissions and rejoin.
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              e.toString().contains('Permission')
                  ? 'Camera/microphone permission denied. Please grant access in Settings.'
                  : 'Could not access camera/microphone: $e',
            ),
            duration: const Duration(seconds: 5),
          ),
        );
      }
    }
  }

  Future<void> _connectWebSocket() async {
    final token = await _storage.getAccessToken();
    if (token == null) return;

    try {
      // The chat service CallConsumer is at ws/calls/ — it's a personal
      // signaling channel per user, NOT per room. The room_id is sent
      // in message bodies (call_invite, call_accept, etc.), not the URL.
      final uri = Uri(
        scheme:          'ws',
        host:            AppConstants.wsHost,
        port:            8002, // chat-service port
        path:            '/ws/calls/',
        queryParameters: {'token': token},
      );

      debugPrint('[VideoCall WS] Connecting to: $uri');

      final channel = WebSocketChannel.connect(uri);

      // Wait for the 101 Switching Protocols handshake to complete.
      // Without this, a rejection throws an unhandled exception.
      await channel.ready;

      _ws = channel;

      _ws!.stream.listen(
        (data) {
          final event = jsonDecode(data as String);
          _handleWsEvent(event);
        },
        onError: (error) {
          debugPrint('[VideoCall WS] Error: $error');
        },
        onDone: () {
          debugPrint('[VideoCall WS] Connection closed');
        },
        cancelOnError: false,
      );

      // Notify the server we're joining this room
      _ws!.sink.add(jsonEncode({
        'type':    'call_invite',
        'room_id': widget.roomId,
        'invited_user_ids': [], // empty = just joining, not inviting anyone
      }));

      // Start heartbeat
      _startHeartbeat();
    } catch (e) {
      debugPrint('[VideoCall WS] Connect failed: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not connect to call server: $e')),
        );
      }
    }
  }

  void _startHeartbeat() {
    Future.delayed(const Duration(seconds: 30), () {
      if (mounted) {
        _ws?.sink.add(jsonEncode({'type': 'heartbeat'}));
        _startHeartbeat();
      }
    });
  }

  Future<void> _handleWsEvent(Map<String, dynamic> event) async {
    switch (event['type']) {
      case 'room_state':
        final participants = List<Map<String, dynamic>>.from(event['participants'] ?? []);
        setState(() => _participants = participants);
        // Create offers for existing participants
        for (final p in participants) {
          await _createOffer(p['user_id'].toString());
        }
        break;

      case 'participant_joined':
        final userId = event['user_id'].toString();
        setState(() => _participants.add(event));
        break;

      case 'participant_left':
        final userId = event['user_id'].toString();
        setState(() => _participants.removeWhere((p) => p['user_id'].toString() == userId));
        _peerConnections[userId]?.close();
        _peerConnections.remove(userId);
        _remoteRenderers[userId]?.dispose();
        _remoteRenderers.remove(userId);
        setState(() {});
        break;

      case 'offer':
        await _handleOffer(event);
        break;

      case 'answer':
        await _handleAnswer(event);
        break;

      case 'ice_candidate':
        await _handleIceCandidate(event);
        break;

      case 'media_state':
        // Update participant media state in UI
        break;
    }
  }

  Future<RTCPeerConnection> _createPeerConnection(String userId) async {
    final config = {
      'iceServers': [
        {'urls': 'stun:stun.l.google.com:19302'},
      ],
    };

    final pc = await createPeerConnection(config);

    // Add local tracks
    _localStream?.getTracks().forEach((track) {
      pc.addTrack(track, _localStream!);
    });

    // Handle remote stream
    pc.onTrack = (event) async {
      if (event.streams.isNotEmpty) {
        final renderer = RTCVideoRenderer();
        await renderer.initialize();
        renderer.srcObject = event.streams[0];
        setState(() => _remoteRenderers[userId] = renderer);
      }
    };

    // Handle ICE candidates
    pc.onIceCandidate = (candidate) {
      _ws?.sink.add(jsonEncode({
        'type': 'ice_candidate',
        'target_user_id': userId,
        'data': candidate.toMap(),
      }));
    };

    _peerConnections[userId] = pc;
    return pc;
  }

  Future<void> _createOffer(String userId) async {
    final pc = await _createPeerConnection(userId);
    final offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    _ws?.sink.add(jsonEncode({
      'type': 'offer',
      'target_user_id': userId,
      'data': offer.toMap(),
    }));
  }

  Future<void> _handleOffer(Map<String, dynamic> event) async {
    final userId = event['from_user_id'].toString();
    final pc = await _createPeerConnection(userId);
    await pc.setRemoteDescription(
      RTCSessionDescription(event['data']['sdp'], event['data']['type']),
    );
    final answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    _ws?.sink.add(jsonEncode({
      'type': 'answer',
      'target_user_id': userId,
      'data': answer.toMap(),
    }));
  }

  Future<void> _handleAnswer(Map<String, dynamic> event) async {
    final userId = event['from_user_id'].toString();
    final pc = _peerConnections[userId];
    if (pc != null) {
      await pc.setRemoteDescription(
        RTCSessionDescription(event['data']['sdp'], event['data']['type']),
      );
    }
  }

  Future<void> _handleIceCandidate(Map<String, dynamic> event) async {
    final userId = event['from_user_id'].toString();
    final pc = _peerConnections[userId];
    if (pc != null) {
      await pc.addCandidate(RTCIceCandidate(
        event['data']['candidate'],
        event['data']['sdpMid'],
        event['data']['sdpMLineIndex'],
      ));
    }
  }

  void _toggleMute() {
    setState(() => _isMuted = !_isMuted);
    _localStream?.getAudioTracks().forEach((t) => t.enabled = !_isMuted);
    _ws?.sink.add(jsonEncode({
      'type': 'media_state',
      'is_muted': _isMuted,
      'is_video_on': !_isCameraOff,
    }));
  }

  void _toggleCamera() {
    setState(() => _isCameraOff = !_isCameraOff);
    _localStream?.getVideoTracks().forEach((t) => t.enabled = !_isCameraOff);
    _ws?.sink.add(jsonEncode({
      'type': 'media_state',
      'is_muted': _isMuted,
      'is_video_on': !_isCameraOff,
    }));
  }

  void _leaveCall() {
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final remoteList = _remoteRenderers.entries.toList();

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          children: [
            // Remote video grid
            remoteList.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.person, size: 80, color: Colors.white54),
                        const SizedBox(height: 16),
                        Text(
                          'Waiting for others to join...',
                          style: TextStyle(color: Colors.white.withOpacity(0.7)),
                        ),
                      ],
                    ),
                  )
                : GridView.builder(
                    padding: const EdgeInsets.all(8),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      crossAxisSpacing: 8,
                      mainAxisSpacing: 8,
                    ),
                    itemCount: remoteList.length,
                    itemBuilder: (context, i) {
                      final entry = remoteList[i];
                      return ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: Stack(
                          fit: StackFit.expand,
                          children: [
                            RTCVideoView(entry.value, objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover),
                            Positioned(
                              bottom: 8,
                              left: 8,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.black54,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  entry.key,
                                  style: const TextStyle(color: Colors.white, fontSize: 12),
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),

            // Local PiP
            Positioned(
              bottom: 100,
              right: 16,
              child: Container(
                width: 100,
                height: 140,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.primary, width: 2),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: _isCameraOff
                      ? Container(
                          color: Colors.grey.shade800,
                          child: const Icon(Icons.videocam_off, color: Colors.white),
                        )
                      : RTCVideoView(_localRenderer, mirror: true),
                ),
              ),
            ),

            // Control bar
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [Colors.black, Colors.transparent],
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _CallButton(
                      icon: _isMuted ? Icons.mic_off : Icons.mic,
                      label: _isMuted ? 'Unmute' : 'Mute',
                      color: _isMuted ? AppColors.danger : Colors.white,
                      onTap: _toggleMute,
                    ),
                    _CallButton(
                      icon: _isCameraOff ? Icons.videocam_off : Icons.videocam,
                      label: _isCameraOff ? 'Start Video' : 'Stop Video',
                      color: _isCameraOff ? AppColors.danger : Colors.white,
                      onTap: _toggleCamera,
                    ),
                    _CallButton(
                      icon: Icons.people,
                      label: '${_participants.length + 1}',
                      color: Colors.white,
                      onTap: () => setState(() => _showParticipants = !_showParticipants),
                    ),
                    _CallButton(
                      icon: Icons.call_end,
                      label: 'Leave',
                      color: AppColors.danger,
                      backgroundColor: AppColors.danger.withOpacity(0.2),
                      onTap: _leaveCall,
                    ),
                  ],
                ),
              ),
            ),

            // Participants panel
            if (_showParticipants)
              Positioned(
                bottom: 80,
                left: 0,
                right: 0,
                child: Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.black87,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'Participants',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 8),
                      ..._participants.map((p) => ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: CircleAvatar(
                              backgroundColor: AppColors.primary,
                              child: Text(
                                (p['username'] ?? 'U')[0].toUpperCase(),
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                            title: Text(
                              p['username'] ?? 'Unknown',
                              style: const TextStyle(color: Colors.white),
                            ),
                          )),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _CallButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final Color? backgroundColor;
  final VoidCallback onTap;

  const _CallButton({
    required this.icon,
    required this.label,
    required this.color,
    this.backgroundColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: backgroundColor ?? Colors.white.withOpacity(0.15),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 28),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(color: Colors.white, fontSize: 11),
          ),
        ],
      ),
    );
  }
}
