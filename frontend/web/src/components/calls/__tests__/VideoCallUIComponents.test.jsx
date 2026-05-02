/**
 * UI Component Unit Tests for Video Call Feature
 *
 * Covers:
 * - VideoCallContainer: lifecycle (mount/unmount), cleanup of WebRTC resources
 * - RemoteVideoGrid: layout calculations for 2, 4, 6, 8 participants
 * - RemoteVideoTile: rendering with muted/video-off/screen-sharing states, connection quality
 * - CallControls: mute, video toggle, screen share, leave call button interactions
 * - CallNotification: auto-dismiss after 30 seconds, accept/decline buttons
 *
 * Validates: Requirements 2.1, 2.2, 3.1, 3.2, 5.7
 */

import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// ── Mocks ────────────────────────────────────────────────────────────────────

// Mock WebRTCClient
const mockWebRTCClient = {
  setIceServers: jest.fn(),
  getLocalMediaStream: jest.fn(() => Promise.resolve(null)),
  releaseMediaStreams: jest.fn(),
  toggleAudio: jest.fn(),
  toggleVideo: jest.fn(),
  startScreenShare: jest.fn(() => Promise.resolve(null)),
  stopScreenShare: jest.fn(),
  createOffer: jest.fn(),
  handleOffer: jest.fn(),
  handleAnswer: jest.fn(),
  handleIceCandidate: jest.fn(),
  onRemoteStream: null,
  onRemoteStreamRemoved: null,
  onConnectionQualityChange: null,
  onError: null,
};

jest.mock('@/lib/webrtc/WebRTCClient', () => {
  return jest.fn().mockImplementation(() => mockWebRTCClient);
});

// Mock react-hot-toast
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
  error: jest.fn(),
  success: jest.fn(),
}));

// Mock framer-motion (used by Modal)
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  Mic: () => <span data-testid="icon-mic" />,
  MicOff: () => <span data-testid="icon-mic-off" />,
  Video: () => <span data-testid="icon-video" />,
  VideoOff: () => <span data-testid="icon-video-off" />,
  Monitor: () => <span data-testid="icon-monitor" />,
  MonitorOff: () => <span data-testid="icon-monitor-off" />,
  PhoneOff: () => <span data-testid="icon-phone-off" />,
  Phone: () => <span data-testid="icon-phone" />,
  PhoneMissed: () => <span data-testid="icon-phone-missed" />,
  ChevronLeft: () => <span data-testid="icon-chevron-left" />,
  ChevronRight: () => <span data-testid="icon-chevron-right" />,
  Wifi: () => <span data-testid="icon-wifi" />,
  X: () => <span data-testid="icon-x" />,
}));

// Mock child components used by VideoCallContainer
jest.mock('@/components/calls/LocalVideoPreview', () => ({
  __esModule: true,
  default: ({ stream, user, isMuted, isVideoOff }) => (
    <div data-testid="local-video-preview" data-muted={isMuted} data-video-off={isVideoOff} />
  ),
}));

jest.mock('@/components/calls/ScreenShareDisplay', () => ({
  __esModule: true,
  default: ({ stream, sharerName }) => (
    <div data-testid="screen-share-display" data-sharer={sharerName} />
  ),
}));

// Mock Avatar component
jest.mock('@/components/ui/Avatar', () => ({
  __esModule: true,
  default: ({ name, src }) => <div data-testid="avatar" data-name={name} />,
}));

// Import components under test (after mocks are set up)
import VideoCallContainer from '@/components/calls/VideoCallContainer';
import RemoteVideoGrid from '@/components/calls/RemoteVideoGrid';
import RemoteVideoTile from '@/components/calls/RemoteVideoTile';
import CallControls from '@/components/calls/CallControls';
import CallNotification from '@/components/calls/CallNotification';
import WebRTCClientMock from '@/lib/webrtc/WebRTCClient';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeParticipant(id, name = `User ${id}`) {
  return { id, full_name: name, avatar_url: null };
}

function makeStream(hasVideo = true) {
  const videoTrack = { kind: 'video', enabled: hasVideo };
  return {
    getVideoTracks: jest.fn(() => (hasVideo ? [videoTrack] : [])),
    getAudioTracks: jest.fn(() => [{ kind: 'audio', enabled: true }]),
    getTracks: jest.fn(() => [videoTrack]),
  };
}

// ── VideoCallContainer Tests ─────────────────────────────────────────────────

describe('VideoCallContainer', () => {
  const mockSignalingChannel = { send: jest.fn() };
  const mockUser = { id: 'user-1', full_name: 'Alice', avatar_url: null };
  const mockParticipants = [makeParticipant('user-1', 'Alice'), makeParticipant('user-2', 'Bob')];

  beforeEach(() => {
    jest.clearAllMocks();
    mockWebRTCClient.getLocalMediaStream.mockResolvedValue(null);
  });

  /**
   * Validates: Requirements 2.1
   * Test: VideoCallContainer mounts and initialises WebRTCClient
   */
  test('initialises WebRTCClient on mount', async () => {
    await act(async () => {
      render(
        <VideoCallContainer
          roomId="room-1"
          userId="user-1"
          user={mockUser}
          participants={mockParticipants}
          signalingChannel={mockSignalingChannel}
        />
      );
    });

    expect(WebRTCClientMock).toHaveBeenCalledWith('room-1', 'user-1', mockSignalingChannel);
    expect(mockWebRTCClient.getLocalMediaStream).toHaveBeenCalled();
  });

  /**
   * Validates: Requirements 2.1
   * Test: VideoCallContainer calls releaseMediaStreams on unmount (cleanup)
   */
  test('releases media streams on unmount', async () => {
    let unmount;

    await act(async () => {
      const result = render(
        <VideoCallContainer
          roomId="room-1"
          userId="user-1"
          user={mockUser}
          participants={mockParticipants}
          signalingChannel={mockSignalingChannel}
        />
      );
      unmount = result.unmount;
    });

    act(() => {
      unmount();
    });

    expect(mockWebRTCClient.releaseMediaStreams).toHaveBeenCalled();
  });

  /**
   * Validates: Requirements 2.1
   * Test: VideoCallContainer renders CallControls
   */
  test('renders CallControls bar', async () => {
    await act(async () => {
      render(
        <VideoCallContainer
          roomId="room-1"
          userId="user-1"
          user={mockUser}
          participants={mockParticipants}
          signalingChannel={mockSignalingChannel}
        />
      );
    });

    // CallControls renders mute button
    expect(screen.getByTitle(/mute microphone/i)).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.1
   * Test: VideoCallContainer does not initialise WebRTCClient without signalingChannel
   */
  test('does not initialise WebRTCClient when signalingChannel is absent', async () => {
    WebRTCClientMock.mockClear();

    await act(async () => {
      render(
        <VideoCallContainer
          roomId="room-1"
          userId="user-1"
          user={mockUser}
          participants={mockParticipants}
          signalingChannel={null}
        />
      );
    });

    expect(WebRTCClientMock).not.toHaveBeenCalled();
  });
});

// ── RemoteVideoGrid Tests ────────────────────────────────────────────────────

describe('RemoteVideoGrid', () => {
  function renderGrid(count, streams = {}, participantStates = {}, connectionQualities = {}) {
    const participants = Array.from({ length: count }, (_, i) =>
      makeParticipant(`user-${i + 1}`, `User ${i + 1}`)
    );
    return render(
      <RemoteVideoGrid
        participants={participants}
        streams={streams}
        participantStates={participantStates}
        connectionQualities={connectionQualities}
      />
    );
  }

  /**
   * Validates: Requirements 2.2
   * Test: 2 participants renders grid-cols-2
   */
  test('renders grid-cols-2 for 2 participants', () => {
    const { container } = renderGrid(2);
    const grid = container.querySelector('.grid');
    expect(grid).toHaveClass('grid-cols-2');
  });

  /**
   * Validates: Requirements 2.2
   * Test: 4 participants renders grid-cols-2
   */
  test('renders grid-cols-2 for 4 participants', () => {
    const { container } = renderGrid(4);
    const grid = container.querySelector('.grid');
    expect(grid).toHaveClass('grid-cols-2');
  });

  /**
   * Validates: Requirements 2.2
   * Test: 6 participants shows pagination with 2 pages
   */
  test('shows 2 pages for 6 participants', () => {
    renderGrid(6);
    // Page indicator shows 1 / 2
    expect(screen.getByText('1 / 2')).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.2
   * Test: 8 participants renders grid-cols-3 (first page shows 4, grid based on page count)
   */
  test('renders grid-cols-2 for first page of 8 participants (4 tiles visible)', () => {
    const { container } = renderGrid(8);
    const grid = container.querySelector('.grid');
    // First page shows 4 tiles → grid-cols-2
    expect(grid).toHaveClass('grid-cols-2');
  });

  /**
   * Validates: Requirements 2.2
   * Test: Pagination controls appear when participants > 4
   */
  test('shows pagination controls for more than 4 participants', () => {
    renderGrid(6);
    expect(screen.getByLabelText('Next page')).toBeInTheDocument();
    expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.2
   * Test: No pagination controls for 4 or fewer participants
   */
  test('hides pagination controls for 4 or fewer participants', () => {
    renderGrid(4);
    expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.2
   * Test: Pagination navigates to next page
   */
  test('navigates to next page on next button click', () => {
    renderGrid(6);
    const nextBtn = screen.getByLabelText('Next page');
    fireEvent.click(nextBtn);
    // Page indicator should show 2 / 2
    expect(screen.getByText('2 / 2')).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.2
   * Test: Previous button is disabled on first page
   */
  test('previous button is disabled on first page', () => {
    renderGrid(6);
    expect(screen.getByLabelText('Previous page')).toBeDisabled();
  });

  /**
   * Validates: Requirements 2.2
   * Test: Renders correct number of tiles on first page
   */
  test('renders up to 4 tiles on first page', () => {
    const { container } = renderGrid(8);
    // RemoteVideoTile renders a div with relative class
    const tiles = container.querySelectorAll('.relative.bg-bg-panel');
    expect(tiles.length).toBe(4);
  });
});

// ── RemoteVideoTile Tests ────────────────────────────────────────────────────

describe('RemoteVideoTile', () => {
  const participant = makeParticipant('user-2', 'Bob');

  /**
   * Validates: Requirements 2.4, 2.5
   * Test: Renders participant name
   */
  test('renders participant name', () => {
    render(
      <RemoteVideoTile
        userId="user-2"
        stream={null}
        participant={participant}
      />
    );
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 3.5
   * Test: Shows muted indicator when isMuted is true
   */
  test('shows muted indicator when participant is muted', () => {
    render(
      <RemoteVideoTile
        userId="user-2"
        stream={null}
        participant={participant}
        isMuted={true}
      />
    );
    expect(screen.getByTestId('icon-mic-off')).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 3.5
   * Test: Does not show muted indicator when not muted
   */
  test('does not show muted indicator when participant is not muted', () => {
    render(
      <RemoteVideoTile
        userId="user-2"
        stream={null}
        participant={participant}
        isMuted={false}
      />
    );
    expect(screen.queryByTestId('icon-mic-off')).not.toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.5
   * Test: Shows avatar and "Camera off" text when video is off
   */
  test('shows avatar and camera-off label when video is off', () => {
    render(
      <RemoteVideoTile
        userId="user-2"
        stream={null}
        participant={participant}
        isVideoOff={true}
      />
    );
    expect(screen.getByText('Camera off')).toBeInTheDocument();
    expect(screen.getByTestId('avatar')).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.4
   * Test: Renders video element when stream has video and video is on
   */
  test('renders video element when stream has active video track', () => {
    const stream = makeStream(true);
    const { container } = render(
      <RemoteVideoTile
        userId="user-2"
        stream={stream}
        participant={participant}
        isVideoOff={false}
      />
    );
    expect(container.querySelector('video')).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.4
   * Test: Does not render video element when video is off
   */
  test('does not render video element when isVideoOff is true', () => {
    const stream = makeStream(true);
    const { container } = render(
      <RemoteVideoTile
        userId="user-2"
        stream={stream}
        participant={participant}
        isVideoOff={true}
      />
    );
    expect(container.querySelector('video')).not.toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.6
   * Test: Shows connection quality indicator when quality is provided
   */
  test('shows connection quality indicator for good quality', () => {
    render(
      <RemoteVideoTile
        userId="user-2"
        stream={null}
        participant={participant}
        connectionQuality={{ quality: 'good' }}
      />
    );
    expect(screen.getByTestId('icon-wifi')).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.6
   * Test: Shows connection quality indicator for poor quality
   */
  test('shows connection quality indicator for poor quality', () => {
    const { container } = render(
      <RemoteVideoTile
        userId="user-2"
        stream={null}
        participant={participant}
        connectionQuality={{ quality: 'poor' }}
      />
    );
    expect(screen.getByTestId('icon-wifi')).toBeInTheDocument();
    // Poor quality uses red color class
    const qualityDiv = container.querySelector('.text-red-400');
    expect(qualityDiv).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.6
   * Test: Does not show quality indicator when connectionQuality is null
   */
  test('does not show quality indicator when connectionQuality is null', () => {
    render(
      <RemoteVideoTile
        userId="user-2"
        stream={null}
        participant={participant}
        connectionQuality={null}
      />
    );
    expect(screen.queryByTestId('icon-wifi')).not.toBeInTheDocument();
  });

  /**
   * Validates: Requirements 2.5
   * Test: Falls back to "Participant" when participant name is missing
   */
  test('falls back to "Participant" label when no name provided', () => {
    render(
      <RemoteVideoTile
        userId="user-2"
        stream={null}
        participant={{}}
      />
    );
    expect(screen.getByText('Participant')).toBeInTheDocument();
  });
});

// ── CallControls Tests ───────────────────────────────────────────────────────

describe('CallControls', () => {
  /**
   * Validates: Requirements 3.1
   * Test: Mute button calls onToggleAudio
   */
  test('calls onToggleAudio when mute button is clicked', () => {
    const onToggleAudio = jest.fn();
    render(
      <CallControls
        audioEnabled={true}
        videoEnabled={true}
        screenSharing={false}
        onToggleAudio={onToggleAudio}
        onToggleVideo={jest.fn()}
        onToggleScreen={jest.fn()}
        onLeave={jest.fn()}
      />
    );

    fireEvent.click(screen.getByTitle(/mute microphone/i));
    expect(onToggleAudio).toHaveBeenCalledTimes(1);
  });

  /**
   * Validates: Requirements 3.2
   * Test: Video toggle button calls onToggleVideo
   */
  test('calls onToggleVideo when video button is clicked', () => {
    const onToggleVideo = jest.fn();
    render(
      <CallControls
        audioEnabled={true}
        videoEnabled={true}
        screenSharing={false}
        onToggleAudio={jest.fn()}
        onToggleVideo={onToggleVideo}
        onToggleScreen={jest.fn()}
        onLeave={jest.fn()}
      />
    );

    fireEvent.click(screen.getByTitle(/turn off camera/i));
    expect(onToggleVideo).toHaveBeenCalledTimes(1);
  });

  /**
   * Validates: Requirements 3.1
   * Test: Shows unmute label when audio is disabled
   */
  test('shows unmute label when audio is disabled', () => {
    render(
      <CallControls
        audioEnabled={false}
        videoEnabled={true}
        screenSharing={false}
        onToggleAudio={jest.fn()}
        onToggleVideo={jest.fn()}
        onToggleScreen={jest.fn()}
        onLeave={jest.fn()}
      />
    );
    expect(screen.getByTitle(/unmute microphone/i)).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 3.2
   * Test: Shows turn-on-camera label when video is disabled
   */
  test('shows turn-on-camera label when video is disabled', () => {
    render(
      <CallControls
        audioEnabled={true}
        videoEnabled={false}
        screenSharing={false}
        onToggleAudio={jest.fn()}
        onToggleVideo={jest.fn()}
        onToggleScreen={jest.fn()}
        onLeave={jest.fn()}
      />
    );
    expect(screen.getByTitle(/turn on camera/i)).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 3.3
   * Test: Screen share button calls onToggleScreen
   */
  test('calls onToggleScreen when screen share button is clicked', () => {
    const onToggleScreen = jest.fn();
    render(
      <CallControls
        audioEnabled={true}
        videoEnabled={true}
        screenSharing={false}
        onToggleAudio={jest.fn()}
        onToggleVideo={jest.fn()}
        onToggleScreen={onToggleScreen}
        onLeave={jest.fn()}
      />
    );

    fireEvent.click(screen.getByTitle(/share screen/i));
    expect(onToggleScreen).toHaveBeenCalledTimes(1);
  });

  /**
   * Validates: Requirements 3.4
   * Test: Leave button opens confirmation dialog
   */
  test('opens leave confirmation dialog when leave button is clicked', () => {
    render(
      <CallControls
        audioEnabled={true}
        videoEnabled={true}
        screenSharing={false}
        onToggleAudio={jest.fn()}
        onToggleVideo={jest.fn()}
        onToggleScreen={jest.fn()}
        onLeave={jest.fn()}
      />
    );

    fireEvent.click(screen.getByTitle(/leave call/i));
    expect(screen.getByText(/are you sure you want to leave/i)).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 3.4
   * Test: Confirming leave calls onLeave
   */
  test('calls onLeave when leave is confirmed in dialog', () => {
    const onLeave = jest.fn();
    render(
      <CallControls
        audioEnabled={true}
        videoEnabled={true}
        screenSharing={false}
        onToggleAudio={jest.fn()}
        onToggleVideo={jest.fn()}
        onToggleScreen={jest.fn()}
        onLeave={onLeave}
      />
    );

    fireEvent.click(screen.getByTitle(/leave call/i));
    fireEvent.click(screen.getByRole('button', { name: /^leave$/i }));
    expect(onLeave).toHaveBeenCalledTimes(1);
  });

  /**
   * Validates: Requirements 3.4
   * Test: Cancelling leave dialog does not call onLeave
   */
  test('does not call onLeave when leave is cancelled', () => {
    const onLeave = jest.fn();
    render(
      <CallControls
        audioEnabled={true}
        videoEnabled={true}
        screenSharing={false}
        onToggleAudio={jest.fn()}
        onToggleVideo={jest.fn()}
        onToggleScreen={jest.fn()}
        onLeave={onLeave}
      />
    );

    fireEvent.click(screen.getByTitle(/leave call/i));
    fireEvent.click(screen.getByRole('button', { name: /stay/i }));
    expect(onLeave).not.toHaveBeenCalled();
  });

  /**
   * Validates: Requirements 3.3
   * Test: Screen share button shows stop-sharing label when active
   */
  test('shows stop-sharing label when screen sharing is active', () => {
    render(
      <CallControls
        audioEnabled={true}
        videoEnabled={true}
        screenSharing={true}
        onToggleAudio={jest.fn()}
        onToggleVideo={jest.fn()}
        onToggleScreen={jest.fn()}
        onLeave={jest.fn()}
      />
    );
    expect(screen.getByTitle(/stop sharing screen/i)).toBeInTheDocument();
  });
});

// ── CallNotification Tests ───────────────────────────────────────────────────

describe('CallNotification', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    act(() => {
      jest.runOnlyPendingTimers();
    });
    jest.useRealTimers();
  });

  /**
   * Validates: Requirements 5.2, 5.3
   * Test: Renders caller name and action buttons
   */
  test('renders caller name and accept/decline buttons', () => {
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        onAccept={jest.fn()}
        onDecline={jest.fn()}
      />
    );

    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /decline/i })).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 5.4
   * Test: Accept button calls onAccept
   */
  test('calls onAccept when accept button is clicked', () => {
    const onAccept = jest.fn();
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        onAccept={onAccept}
        onDecline={jest.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /accept/i }));
    expect(onAccept).toHaveBeenCalledTimes(1);
  });

  /**
   * Validates: Requirements 5.5
   * Test: Decline button calls onDecline
   */
  test('calls onDecline when decline button is clicked', () => {
    const onDecline = jest.fn();
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        onAccept={jest.fn()}
        onDecline={onDecline}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /decline/i }));
    expect(onDecline).toHaveBeenCalledTimes(1);
  });

  /**
   * Validates: Requirements 5.7
   * Test: Auto-dismisses (calls onDecline) after 30 seconds
   */
  test('auto-dismisses by calling onDecline after 30 seconds', () => {
    const onDecline = jest.fn();
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        onAccept={jest.fn()}
        onDecline={onDecline}
        autoDismissTimeout={30000}
      />
    );

    // Advance 30 seconds (30 ticks of 1s interval)
    act(() => {
      jest.advanceTimersByTime(30000);
    });

    expect(onDecline).toHaveBeenCalledTimes(1);
  });

  /**
   * Validates: Requirements 5.7
   * Test: Countdown timer is visible and decrements
   */
  test('shows countdown timer that decrements each second', () => {
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        onAccept={jest.fn()}
        onDecline={jest.fn()}
        autoDismissTimeout={30000}
      />
    );

    expect(screen.getByText(/30s/)).toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(1000);
    });

    expect(screen.getByText(/29s/)).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 5.6
   * Test: Shows busy indicator when isBusy is true
   */
  test('shows busy indicator when user is already in a call', () => {
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        isBusy={true}
        onAccept={jest.fn()}
        onDecline={jest.fn()}
      />
    );

    expect(screen.getByText(/you're currently in a call/i)).toBeInTheDocument();
  });

  /**
   * Validates: Requirements 5.6
   * Test: Accept button is disabled when isBusy is true
   */
  test('accept button is disabled when user is busy', () => {
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        isBusy={true}
        onAccept={jest.fn()}
        onDecline={jest.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /busy/i })).toBeDisabled();
  });

  /**
   * Validates: Requirements 5.7
   * Test: Does not auto-dismiss before 30 seconds
   */
  test('does not auto-dismiss before 30 seconds have elapsed', () => {
    const onDecline = jest.fn();
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        onAccept={jest.fn()}
        onDecline={onDecline}
        autoDismissTimeout={30000}
      />
    );

    act(() => {
      jest.advanceTimersByTime(29000);
    });

    expect(onDecline).not.toHaveBeenCalled();
  });

  /**
   * Validates: Requirements 5.7
   * Test: Accepts custom autoDismissTimeout
   */
  test('auto-dismisses after custom timeout', () => {
    const onDecline = jest.fn();
    render(
      <CallNotification
        callerId="user-2"
        callerName="Bob"
        roomId="room-1"
        onAccept={jest.fn()}
        onDecline={onDecline}
        autoDismissTimeout={5000}
      />
    );

    act(() => {
      jest.advanceTimersByTime(5000);
    });

    expect(onDecline).toHaveBeenCalledTimes(1);
  });
});
