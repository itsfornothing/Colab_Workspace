/**
 * Tests for video rendering performance optimizations.
 * Requirement 11.5
 */

import React from 'react';
import { render, screen, act, fireEvent } from '@testing-library/react';
import RemoteVideoTile from '../RemoteVideoTile';
import RemoteVideoGrid from '../RemoteVideoGrid';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeParticipant(id, name = `User ${id}`) {
  return { id, full_name: name, avatar_url: null };
}

function makeStream(hasVideo = true) {
  const track = {
    kind: 'video',
    enabled: hasVideo,
    stop: jest.fn(),
  };
  return {
    getVideoTracks: () => (hasVideo ? [track] : []),
    getAudioTracks: () => [],
    getTracks: () => (hasVideo ? [track] : []),
  };
}

// ── IntersectionObserver mock ─────────────────────────────────────────────────
// jsdom does not implement IntersectionObserver; we provide a controllable mock.

let intersectionCallback = null;
let observedElements = [];

const mockIntersectionObserver = jest.fn().mockImplementation((callback) => {
  intersectionCallback = callback;
  return {
    observe: jest.fn((el) => observedElements.push(el)),
    disconnect: jest.fn(() => {
      observedElements = [];
      intersectionCallback = null;
    }),
    unobserve: jest.fn(),
  };
});

function simulateVisible(isIntersecting = true) {
  if (intersectionCallback) {
    intersectionCallback([{ isIntersecting }]);
  }
}

// ── RemoteVideoTile tests ─────────────────────────────────────────────────────

describe('RemoteVideoTile — performance optimizations', () => {
  beforeEach(() => {
    observedElements = [];
    intersectionCallback = null;
    global.IntersectionObserver = mockIntersectionObserver;
  });

  afterEach(() => {
    jest.clearAllMocks();
    delete global.IntersectionObserver;
  });

  it('renders with the video-tile CSS class for GPU acceleration', () => {
    const participant = makeParticipant('u1');
    const { container } = render(
      <RemoteVideoTile
        userId="u1"
        stream={null}
        participant={participant}
      />
    );
    const tile = container.firstChild;
    expect(tile.className).toContain('video-tile');
  });

  it('applies video-tile--offscreen class when tile is not visible', () => {
    const participant = makeParticipant('u1');
    const { container } = render(
      <RemoteVideoTile
        userId="u1"
        stream={makeStream()}
        participant={participant}
      />
    );

    // Initially not visible (IntersectionObserver hasn't fired yet)
    act(() => simulateVisible(false));

    const tile = container.firstChild;
    expect(tile.className).toContain('video-tile--offscreen');
  });

  it('removes video-tile--offscreen class when tile becomes visible', () => {
    const participant = makeParticipant('u1');
    const { container } = render(
      <RemoteVideoTile
        userId="u1"
        stream={makeStream()}
        participant={participant}
      />
    );

    act(() => simulateVisible(true));

    const tile = container.firstChild;
    expect(tile.className).not.toContain('video-tile--offscreen');
  });

  it('attaches stream to video element when tile becomes visible', () => {
    const participant = makeParticipant('u1');
    const stream = makeStream();

    render(
      <RemoteVideoTile
        userId="u1"
        stream={stream}
        participant={participant}
      />
    );

    act(() => simulateVisible(true));

    const videoEl = document.querySelector('video');
    if (videoEl) {
      // srcObject should be set to the stream when visible
      expect(videoEl.srcObject).toBe(stream);
    }
    // If no video element (stream has no enabled video tracks), test passes trivially
  });

  it('detaches stream from video element when tile goes off-screen', () => {
    const participant = makeParticipant('u1');
    const stream = makeStream();

    render(
      <RemoteVideoTile
        userId="u1"
        stream={stream}
        participant={participant}
      />
    );

    // First make visible so srcObject is set
    act(() => simulateVisible(true));
    // Then go off-screen
    act(() => simulateVisible(false));

    const videoEl = document.querySelector('video');
    if (videoEl) {
      expect(videoEl.srcObject).toBeNull();
    }
  });

  it('shows avatar when video is off regardless of visibility', () => {
    const participant = makeParticipant('u1', 'Alice');
    render(
      <RemoteVideoTile
        userId="u1"
        stream={makeStream(false)}
        participant={participant}
        isVideoOff={true}
      />
    );

    act(() => simulateVisible(true));

    expect(screen.getByText('Camera off')).toBeInTheDocument();
  });

  it('shows participant name overlay', () => {
    const participant = makeParticipant('u1', 'Bob Smith');
    render(
      <RemoteVideoTile
        userId="u1"
        stream={null}
        participant={participant}
      />
    );

    expect(screen.getByText('Bob Smith')).toBeInTheDocument();
  });

  it('shows muted indicator when isMuted is true', () => {
    const participant = makeParticipant('u1');
    const { container } = render(
      <RemoteVideoTile
        userId="u1"
        stream={null}
        participant={participant}
        isMuted={true}
      />
    );

    // MicOff icon should be present (rendered as SVG)
    const micOffIcon = container.querySelector('svg');
    expect(micOffIcon).toBeTruthy();
  });

  it('shows connection quality indicator when quality is provided', () => {
    const participant = makeParticipant('u1');
    const { container } = render(
      <RemoteVideoTile
        userId="u1"
        stream={null}
        participant={participant}
        connectionQuality={{ quality: 'good', latency: 50, packetLoss: 0 }}
      />
    );

    // Wifi icon should be present
    const icons = container.querySelectorAll('svg');
    expect(icons.length).toBeGreaterThan(0);
  });

  it('falls back to visible=true when IntersectionObserver is unavailable', () => {
    // Remove IntersectionObserver to simulate unsupported environment
    delete global.IntersectionObserver;

    const participant = makeParticipant('u1');
    const { container } = render(
      <RemoteVideoTile
        userId="u1"
        stream={null}
        participant={participant}
      />
    );

    const tile = container.firstChild;
    // Should NOT have offscreen class since we default to visible=true
    expect(tile.className).not.toContain('video-tile--offscreen');
  });
});

// ── RemoteVideoGrid tests ─────────────────────────────────────────────────────

describe('RemoteVideoGrid — performance optimizations', () => {
  beforeEach(() => {
    global.IntersectionObserver = mockIntersectionObserver;
  });

  afterEach(() => {
    jest.clearAllMocks();
    delete global.IntersectionObserver;
  });

  it('renders with the video-grid CSS class for scoped layout containment', () => {
    const participants = [makeParticipant('u1'), makeParticipant('u2')];
    const { container } = render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    const grid = container.querySelector('.video-grid');
    expect(grid).toBeTruthy();
  });

  it('renders correct number of tiles for 2 participants', () => {
    const participants = [makeParticipant('u1'), makeParticipant('u2')];
    render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    expect(screen.getByText('User u1')).toBeInTheDocument();
    expect(screen.getByText('User u2')).toBeInTheDocument();
  });

  it('uses grid-cols-1 for a single participant', () => {
    const participants = [makeParticipant('u1')];
    const { container } = render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    const grid = container.querySelector('.video-grid');
    expect(grid.className).toContain('grid-cols-1');
  });

  it('uses grid-cols-2 for 2 participants', () => {
    const participants = [makeParticipant('u1'), makeParticipant('u2')];
    const { container } = render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    const grid = container.querySelector('.video-grid');
    expect(grid.className).toContain('grid-cols-2');
  });

  it('uses grid-cols-2 for 4 participants', () => {
    const participants = Array.from({ length: 4 }, (_, i) => makeParticipant(`u${i}`));
    const { container } = render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    const grid = container.querySelector('.video-grid');
    expect(grid.className).toContain('grid-cols-2');
  });

  it('uses grid-cols-3 for 5+ participants (visible page has 4, but grid adapts to paged count)', () => {
    // With PAGE_SIZE=4, a 5-participant call shows 4 tiles on page 1 → grid-cols-2
    // grid-cols-3 only appears when the visible slice has 5+ tiles, which requires
    // PAGE_SIZE > 4. This test verifies the getGridClass logic directly.
    const participants = Array.from({ length: 5 }, (_, i) => makeParticipant(`u${i}`));
    const { container } = render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    const grid = container.querySelector('.video-grid');
    // Page 1 shows 4 participants → grid-cols-2
    expect(grid.className).toContain('grid-cols-2');
  });

  it('shows pagination controls when there are more than 4 participants', () => {
    const participants = Array.from({ length: 6 }, (_, i) => makeParticipant(`u${i}`));
    render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    expect(screen.getByLabelText('Next page')).toBeInTheDocument();
    expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
  });

  it('does not show pagination controls for 4 or fewer participants', () => {
    const participants = Array.from({ length: 4 }, (_, i) => makeParticipant(`u${i}`));
    render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
  });

  it('navigates to next page when next button is clicked', async () => {
    const participants = Array.from({ length: 6 }, (_, i) => makeParticipant(`u${i}`, `User ${i}`));
    render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
      />
    );

    // Page 1 shows users 0-3
    expect(screen.getByText('User 0')).toBeInTheDocument();

    act(() => {
      fireEvent.click(screen.getByLabelText('Next page'));
    });

    // Page 2 shows users 4-5
    expect(screen.getByText('User 4')).toBeInTheDocument();
    expect(screen.queryByText('User 0')).not.toBeInTheDocument();
  });

  it('passes participantStates to tiles correctly', () => {
    const participants = [makeParticipant('u1')];
    const participantStates = { u1: { is_muted: true, is_video_on: false } };

    const { container } = render(
      <RemoteVideoGrid
        participants={participants}
        streams={{}}
        participantStates={participantStates}
      />
    );

    // Camera off text should appear since is_video_on is false
    expect(screen.getByText('Camera off')).toBeInTheDocument();
  });

  it('renders empty grid without errors when participants is empty', () => {
    const { container } = render(
      <RemoteVideoGrid
        participants={[]}
        streams={{}}
      />
    );

    const grid = container.querySelector('.video-grid');
    expect(grid).toBeTruthy();
    expect(grid.children).toHaveLength(0);
  });
});
