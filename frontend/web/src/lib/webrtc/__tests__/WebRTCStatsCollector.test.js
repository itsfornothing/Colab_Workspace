/**
 * Tests for WebRTCStatsCollector
 * Requirements: 11.3, 11.5
 */

import WebRTCStatsCollector, { buildSnapshot, MAX_HISTORY_SIZE } from '../WebRTCStatsCollector';

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Build a minimal RTCStatsReport-like iterable from an array of report objects.
 */
function makeStatsReport(reports) {
  const map = new Map();
  reports.forEach((r, i) => map.set(`id-${i}`, r));
  return map;
}

/**
 * Build a mock RTCPeerConnection whose getStats() resolves with the given reports.
 */
function makeMockPeerConnection(reports = []) {
  return {
    getStats: jest.fn().mockResolvedValue(makeStatsReport(reports)),
  };
}

// ── buildSnapshot unit tests ──────────────────────────────────────────────────

describe('buildSnapshot', () => {
  it('returns a snapshot with zero-valued fields when stats report is empty', () => {
    const snapshot = buildSnapshot(makeStatsReport([]));

    expect(snapshot.inboundVideo.packetsReceived).toBe(0);
    expect(snapshot.inboundAudio.packetsReceived).toBe(0);
    expect(snapshot.outboundVideo.packetsSent).toBe(0);
    expect(snapshot.outboundAudio.packetsSent).toBe(0);
    expect(snapshot.candidatePair.currentRoundTripTime).toBeNull();
    expect(snapshot.derived.videoPacketLossPct).toBe(0);
    expect(snapshot.derived.audioPacketLossPct).toBe(0);
    expect(snapshot.derived.latencyMs).toBeNull();
    expect(snapshot.derived.bandwidthKbps).toBeNull();
    expect(typeof snapshot.timestamp).toBe('number');
  });

  it('extracts inbound-rtp video stats correctly', () => {
    const reports = [
      {
        type: 'inbound-rtp',
        kind: 'video',
        packetsReceived: 900,
        packetsLost: 100,
        bytesReceived: 500000,
        framesDecoded: 300,
        framesDropped: 5,
        jitter: 0.02,
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    expect(snapshot.inboundVideo.packetsReceived).toBe(900);
    expect(snapshot.inboundVideo.packetsLost).toBe(100);
    expect(snapshot.inboundVideo.bytesReceived).toBe(500000);
    expect(snapshot.inboundVideo.framesDecoded).toBe(300);
    expect(snapshot.inboundVideo.framesDropped).toBe(5);
    expect(snapshot.inboundVideo.jitter).toBe(0.02);
  });

  it('extracts inbound-rtp audio stats correctly', () => {
    const reports = [
      {
        type: 'inbound-rtp',
        kind: 'audio',
        packetsReceived: 500,
        packetsLost: 10,
        bytesReceived: 80000,
        jitter: 0.005,
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    expect(snapshot.inboundAudio.packetsReceived).toBe(500);
    expect(snapshot.inboundAudio.packetsLost).toBe(10);
    expect(snapshot.inboundAudio.bytesReceived).toBe(80000);
    expect(snapshot.inboundAudio.jitter).toBe(0.005);
  });

  it('extracts outbound-rtp video stats correctly', () => {
    const reports = [
      {
        type: 'outbound-rtp',
        kind: 'video',
        packetsSent: 800,
        bytesSent: 400000,
        framesSent: 250,
        framesEncoded: 260,
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    expect(snapshot.outboundVideo.packetsSent).toBe(800);
    expect(snapshot.outboundVideo.bytesSent).toBe(400000);
    expect(snapshot.outboundVideo.framesSent).toBe(250);
    expect(snapshot.outboundVideo.framesEncoded).toBe(260);
  });

  it('extracts outbound-rtp audio stats correctly', () => {
    const reports = [
      {
        type: 'outbound-rtp',
        kind: 'audio',
        packetsSent: 400,
        bytesSent: 60000,
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    expect(snapshot.outboundAudio.packetsSent).toBe(400);
    expect(snapshot.outboundAudio.bytesSent).toBe(60000);
  });

  it('extracts candidate-pair stats and derives latency and bandwidth', () => {
    const reports = [
      {
        type: 'candidate-pair',
        state: 'succeeded',
        currentRoundTripTime: 0.05,          // 50 ms
        availableOutgoingBitrate: 2000000,
        availableIncomingBitrate: 1500000,   // 1500 kbps
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    expect(snapshot.candidatePair.currentRoundTripTime).toBe(0.05);
    expect(snapshot.candidatePair.availableIncomingBitrate).toBe(1500000);
    expect(snapshot.derived.latencyMs).toBe(50);
    expect(snapshot.derived.bandwidthKbps).toBe(1500);
  });

  it('ignores candidate-pair entries that are not in succeeded state', () => {
    const reports = [
      {
        type: 'candidate-pair',
        state: 'waiting',
        currentRoundTripTime: 0.1,
        availableIncomingBitrate: 999999,
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    expect(snapshot.candidatePair.currentRoundTripTime).toBeNull();
    expect(snapshot.derived.latencyMs).toBeNull();
  });

  it('calculates video packet loss percentage correctly', () => {
    const reports = [
      {
        type: 'inbound-rtp',
        kind: 'video',
        packetsReceived: 90,
        packetsLost: 10,
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    // 10 / (90 + 10) = 10%
    expect(snapshot.derived.videoPacketLossPct).toBeCloseTo(10, 5);
  });

  it('calculates audio packet loss percentage correctly', () => {
    const reports = [
      {
        type: 'inbound-rtp',
        kind: 'audio',
        packetsReceived: 95,
        packetsLost: 5,
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    // 5 / (95 + 5) = 5%
    expect(snapshot.derived.audioPacketLossPct).toBeCloseTo(5, 5);
  });

  it('falls back to bytesReceived for bandwidth when availableIncomingBitrate is absent', () => {
    const reports = [
      {
        type: 'inbound-rtp',
        kind: 'video',
        bytesReceived: 125000, // 125000 * 8 / 1000 = 1000 kbps
      },
    ];
    const snapshot = buildSnapshot(makeStatsReport(reports));

    expect(snapshot.derived.bandwidthKbps).toBe(1000);
  });
});

// ── WebRTCStatsCollector tests ────────────────────────────────────────────────

describe('WebRTCStatsCollector', () => {
  let collector;

  beforeEach(() => {
    collector = new WebRTCStatsCollector();
  });

  // ── collectStats ────────────────────────────────────────────────────────

  describe('collectStats', () => {
    it('stores a snapshot and returns it', async () => {
      const pc = makeMockPeerConnection([
        { type: 'inbound-rtp', kind: 'video', packetsReceived: 100, packetsLost: 5 },
      ]);

      const snapshot = await collector.collectStats('user-1', pc);

      expect(snapshot).toBeDefined();
      expect(snapshot.inboundVideo.packetsReceived).toBe(100);
      expect(snapshot.inboundVideo.packetsLost).toBe(5);
      expect(collector.getStatsHistory('user-1')).toHaveLength(1);
    });

    it('accumulates multiple snapshots for the same peer', async () => {
      const pc = makeMockPeerConnection([]);

      await collector.collectStats('user-1', pc);
      await collector.collectStats('user-1', pc);
      await collector.collectStats('user-1', pc);

      expect(collector.getStatsHistory('user-1')).toHaveLength(3);
    });

    it('stores snapshots independently for different peers', async () => {
      const pc1 = makeMockPeerConnection([]);
      const pc2 = makeMockPeerConnection([]);

      await collector.collectStats('user-1', pc1);
      await collector.collectStats('user-2', pc2);

      expect(collector.getStatsHistory('user-1')).toHaveLength(1);
      expect(collector.getStatsHistory('user-2')).toHaveLength(1);
    });

    it('throws when no peer connection is provided', async () => {
      await expect(collector.collectStats('user-1', null)).rejects.toThrow();
    });

    it('calls peerConnection.getStats()', async () => {
      const pc = makeMockPeerConnection([]);
      await collector.collectStats('user-1', pc);
      expect(pc.getStats).toHaveBeenCalledTimes(1);
    });
  });

  // ── rolling window ──────────────────────────────────────────────────────

  describe('rolling window', () => {
    it(`caps history at MAX_HISTORY_SIZE (${MAX_HISTORY_SIZE}) snapshots`, async () => {
      const pc = makeMockPeerConnection([]);

      for (let i = 0; i < MAX_HISTORY_SIZE + 10; i++) {
        await collector.collectStats('user-1', pc);
      }

      expect(collector.getStatsHistory('user-1')).toHaveLength(MAX_HISTORY_SIZE);
    });

    it('drops the oldest snapshot when the window is full', async () => {
      // Use a counter to give each snapshot a unique timestamp
      let callCount = 0;
      const pc = {
        getStats: jest.fn().mockImplementation(() => {
          callCount++;
          return Promise.resolve(
            makeStatsReport([
              {
                type: 'inbound-rtp',
                kind: 'video',
                packetsReceived: callCount,
                packetsLost: 0,
              },
            ])
          );
        }),
      };

      for (let i = 0; i < MAX_HISTORY_SIZE + 1; i++) {
        await collector.collectStats('user-1', pc);
      }

      const history = collector.getStatsHistory('user-1');
      expect(history).toHaveLength(MAX_HISTORY_SIZE);
      // The first snapshot (packetsReceived === 1) should have been evicted
      expect(history[0].inboundVideo.packetsReceived).toBe(2);
      // The last snapshot should be the most recent
      expect(history[MAX_HISTORY_SIZE - 1].inboundVideo.packetsReceived).toBe(
        MAX_HISTORY_SIZE + 1
      );
    });
  });

  // ── getStatsHistory ─────────────────────────────────────────────────────

  describe('getStatsHistory', () => {
    it('returns an empty array for an unknown peer', () => {
      expect(collector.getStatsHistory('unknown')).toEqual([]);
    });

    it('returns snapshots in insertion order (oldest first)', async () => {
      let counter = 0;
      const pc = {
        getStats: jest.fn().mockImplementation(() => {
          counter++;
          return Promise.resolve(
            makeStatsReport([
              { type: 'inbound-rtp', kind: 'video', packetsReceived: counter, packetsLost: 0 },
            ])
          );
        }),
      };

      await collector.collectStats('user-1', pc);
      await collector.collectStats('user-1', pc);

      const history = collector.getStatsHistory('user-1');
      expect(history[0].inboundVideo.packetsReceived).toBe(1);
      expect(history[1].inboundVideo.packetsReceived).toBe(2);
    });
  });

  // ── getAllStats ─────────────────────────────────────────────────────────

  describe('getAllStats', () => {
    it('returns an empty object when no stats have been collected', () => {
      expect(collector.getAllStats()).toEqual({});
    });

    it('returns stats for all tracked peers', async () => {
      const pc = makeMockPeerConnection([]);

      await collector.collectStats('user-1', pc);
      await collector.collectStats('user-2', pc);

      const all = collector.getAllStats();
      expect(Object.keys(all)).toHaveLength(2);
      expect(all['user-1']).toHaveLength(1);
      expect(all['user-2']).toHaveLength(1);
    });
  });

  // ── clearStats ──────────────────────────────────────────────────────────

  describe('clearStats', () => {
    it('removes history for the specified peer', async () => {
      const pc = makeMockPeerConnection([]);
      await collector.collectStats('user-1', pc);
      await collector.collectStats('user-2', pc);

      collector.clearStats('user-1');

      expect(collector.getStatsHistory('user-1')).toEqual([]);
      expect(collector.getStatsHistory('user-2')).toHaveLength(1);
    });

    it('is a no-op for an unknown peer', () => {
      expect(() => collector.clearStats('nonexistent')).not.toThrow();
    });
  });

  // ── clearAllStats ───────────────────────────────────────────────────────

  describe('clearAllStats', () => {
    it('removes all stored stats', async () => {
      const pc = makeMockPeerConnection([]);
      await collector.collectStats('user-1', pc);
      await collector.collectStats('user-2', pc);

      collector.clearAllStats();

      expect(collector.getAllStats()).toEqual({});
    });
  });

  // ── logStatsReport ──────────────────────────────────────────────────────

  describe('logStatsReport', () => {
    beforeEach(() => {
      jest.spyOn(console, 'log').mockImplementation(() => {});
    });

    afterEach(() => {
      console.log.mockRestore();
    });

    it('logs a message when no stats are available for the peer', () => {
      collector.logStatsReport('user-1');
      expect(console.log).toHaveBeenCalledWith(
        expect.stringContaining('No stats available')
      );
    });

    it('logs a structured report when stats are available', async () => {
      const pc = makeMockPeerConnection([
        {
          type: 'candidate-pair',
          state: 'succeeded',
          currentRoundTripTime: 0.04,
          availableIncomingBitrate: 2000000,
        },
        {
          type: 'inbound-rtp',
          kind: 'video',
          packetsReceived: 100,
          packetsLost: 2,
        },
      ]);

      await collector.collectStats('user-1', pc);
      collector.logStatsReport('user-1');

      expect(console.log).toHaveBeenCalledWith(
        expect.stringContaining('user-1'),
        expect.objectContaining({
          derived: expect.objectContaining({
            latencyMs: 40,
            bandwidthKbps: 2000,
          }),
        })
      );
    });

    it('includes historySize in the log object', async () => {
      const pc = makeMockPeerConnection([]);
      await collector.collectStats('user-1', pc);
      await collector.collectStats('user-1', pc);

      collector.logStatsReport('user-1');

      expect(console.log).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ historySize: 2 })
      );
    });
  });

  // ── logAllStatsReports ──────────────────────────────────────────────────

  describe('logAllStatsReports', () => {
    beforeEach(() => {
      jest.spyOn(console, 'log').mockImplementation(() => {});
    });

    afterEach(() => {
      console.log.mockRestore();
    });

    it('logs a "no stats" message when nothing has been collected', () => {
      collector.logAllStatsReports();
      expect(console.log).toHaveBeenCalledWith(
        expect.stringContaining('No stats collected')
      );
    });

    it('calls logStatsReport for each tracked peer', async () => {
      const pc = makeMockPeerConnection([]);
      await collector.collectStats('user-1', pc);
      await collector.collectStats('user-2', pc);

      const spy = jest.spyOn(collector, 'logStatsReport');
      collector.logAllStatsReports();

      expect(spy).toHaveBeenCalledWith('user-1');
      expect(spy).toHaveBeenCalledWith('user-2');
    });
  });
});
