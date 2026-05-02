/**
 * WebRTCStatsCollector
 *
 * Collects, stores, and logs detailed WebRTC connection statistics for
 * performance analysis. Works alongside WebRTCClient's existing quality
 * monitoring without replacing it.
 *
 * Requirements: 11.3, 11.5
 */

/** Maximum number of snapshots retained per peer (rolling window ~2 min at 2s interval). */
const MAX_HISTORY_SIZE = 60;

/**
 * Extract a single numeric stat value from an RTCStatsReport by type and field.
 * Returns undefined when the stat is not present.
 *
 * @param {RTCStatsReport} statsReport
 * @param {string} reportType  - e.g. 'inbound-rtp'
 * @param {string} kind        - 'audio' | 'video' | null (skip kind check)
 * @param {string} field       - field name on the report entry
 * @returns {number|undefined}
 */
function extractStat(statsReport, reportType, kind, field) {
  for (const report of statsReport.values()) {
    if (report.type !== reportType) continue;
    if (kind !== null && report.kind !== kind) continue;
    if (field in report) return report[field];
  }
  return undefined;
}

/**
 * Build a structured snapshot from a raw RTCStatsReport.
 *
 * @param {RTCStatsReport} statsReport
 * @returns {Object} snapshot
 */
function buildSnapshot(statsReport) {
  const snapshot = {
    timestamp: Date.now(),

    // ── Inbound video ──────────────────────────────────────────────────────
    inboundVideo: {
      packetsReceived: 0,
      packetsLost: 0,
      bytesReceived: 0,
      framesDecoded: 0,
      framesDropped: 0,
      jitter: 0,
    },

    // ── Inbound audio ──────────────────────────────────────────────────────
    inboundAudio: {
      packetsReceived: 0,
      packetsLost: 0,
      bytesReceived: 0,
      jitter: 0,
    },

    // ── Outbound video ─────────────────────────────────────────────────────
    outboundVideo: {
      packetsSent: 0,
      bytesSent: 0,
      framesSent: 0,
      framesEncoded: 0,
    },

    // ── Outbound audio ─────────────────────────────────────────────────────
    outboundAudio: {
      packetsSent: 0,
      bytesSent: 0,
    },

    // ── Candidate pair ─────────────────────────────────────────────────────
    candidatePair: {
      currentRoundTripTime: null,
      availableOutgoingBitrate: null,
      availableIncomingBitrate: null,
    },

    // ── Derived metrics ────────────────────────────────────────────────────
    derived: {
      videoPacketLossPct: 0,
      audioPacketLossPct: 0,
      latencyMs: null,
      bandwidthKbps: null,
    },
  };

  for (const report of statsReport.values()) {
    switch (report.type) {
      case 'inbound-rtp':
        if (report.kind === 'video') {
          snapshot.inboundVideo.packetsReceived = report.packetsReceived ?? 0;
          snapshot.inboundVideo.packetsLost     = report.packetsLost     ?? 0;
          snapshot.inboundVideo.bytesReceived   = report.bytesReceived   ?? 0;
          snapshot.inboundVideo.framesDecoded   = report.framesDecoded   ?? 0;
          snapshot.inboundVideo.framesDropped   = report.framesDropped   ?? 0;
          snapshot.inboundVideo.jitter          = report.jitter          ?? 0;
        } else if (report.kind === 'audio') {
          snapshot.inboundAudio.packetsReceived = report.packetsReceived ?? 0;
          snapshot.inboundAudio.packetsLost     = report.packetsLost     ?? 0;
          snapshot.inboundAudio.bytesReceived   = report.bytesReceived   ?? 0;
          snapshot.inboundAudio.jitter          = report.jitter          ?? 0;
        }
        break;

      case 'outbound-rtp':
        if (report.kind === 'video') {
          snapshot.outboundVideo.packetsSent   = report.packetsSent   ?? 0;
          snapshot.outboundVideo.bytesSent     = report.bytesSent     ?? 0;
          snapshot.outboundVideo.framesSent    = report.framesSent    ?? 0;
          snapshot.outboundVideo.framesEncoded = report.framesEncoded ?? 0;
        } else if (report.kind === 'audio') {
          snapshot.outboundAudio.packetsSent = report.packetsSent ?? 0;
          snapshot.outboundAudio.bytesSent   = report.bytesSent   ?? 0;
        }
        break;

      case 'candidate-pair':
        if (report.state === 'succeeded') {
          snapshot.candidatePair.currentRoundTripTime    = report.currentRoundTripTime    ?? null;
          snapshot.candidatePair.availableOutgoingBitrate = report.availableOutgoingBitrate ?? null;
          snapshot.candidatePair.availableIncomingBitrate = report.availableIncomingBitrate ?? null;
        }
        break;

      default:
        break;
    }
  }

  // ── Derived: video packet loss % ──────────────────────────────────────
  const totalVideoPackets =
    snapshot.inboundVideo.packetsReceived + snapshot.inboundVideo.packetsLost;
  if (totalVideoPackets > 0) {
    snapshot.derived.videoPacketLossPct =
      (snapshot.inboundVideo.packetsLost / totalVideoPackets) * 100;
  }

  // ── Derived: audio packet loss % ──────────────────────────────────────
  const totalAudioPackets =
    snapshot.inboundAudio.packetsReceived + snapshot.inboundAudio.packetsLost;
  if (totalAudioPackets > 0) {
    snapshot.derived.audioPacketLossPct =
      (snapshot.inboundAudio.packetsLost / totalAudioPackets) * 100;
  }

  // ── Derived: latency (ms) ─────────────────────────────────────────────
  if (snapshot.candidatePair.currentRoundTripTime !== null) {
    snapshot.derived.latencyMs =
      Math.round(snapshot.candidatePair.currentRoundTripTime * 1000);
  }

  // ── Derived: bandwidth (kbps) — prefer availableIncomingBitrate ───────
  if (snapshot.candidatePair.availableIncomingBitrate !== null) {
    snapshot.derived.bandwidthKbps = Math.round(
      snapshot.candidatePair.availableIncomingBitrate / 1000
    );
  } else if (snapshot.inboundVideo.bytesReceived > 0) {
    // Rough estimate from bytes received (not time-normalised, use as fallback)
    snapshot.derived.bandwidthKbps = Math.round(
      (snapshot.inboundVideo.bytesReceived * 8) / 1000
    );
  }

  return snapshot;
}

class WebRTCStatsCollector {
  constructor() {
    /**
     * History map: remoteUserId -> Array<snapshot>
     * Each array is capped at MAX_HISTORY_SIZE (rolling window).
     */
    this._history = new Map();
  }

  /**
   * Collect a stats snapshot for a peer connection and store it.
   *
   * @param {string} remoteUserId
   * @param {RTCPeerConnection} peerConnection
   * @returns {Promise<Object>} The collected snapshot
   */
  async collectStats(remoteUserId, peerConnection) {
    if (!peerConnection) {
      throw new Error(`collectStats: no peer connection provided for ${remoteUserId}`);
    }

    const statsReport = await peerConnection.getStats();
    const snapshot = buildSnapshot(statsReport);

    if (!this._history.has(remoteUserId)) {
      this._history.set(remoteUserId, []);
    }

    const history = this._history.get(remoteUserId);
    history.push(snapshot);

    // Enforce rolling window
    if (history.length > MAX_HISTORY_SIZE) {
      history.shift();
    }

    return snapshot;
  }

  /**
   * Return the stored stats history for a peer.
   *
   * @param {string} remoteUserId
   * @returns {Array<Object>} Array of snapshots (oldest first)
   */
  getStatsHistory(remoteUserId) {
    return this._history.get(remoteUserId) ?? [];
  }

  /**
   * Return all stored stats keyed by remoteUserId.
   *
   * @returns {Object} { [remoteUserId]: Array<snapshot> }
   */
  getAllStats() {
    const result = {};
    for (const [userId, history] of this._history.entries()) {
      result[userId] = history;
    }
    return result;
  }

  /**
   * Clear stored stats for a specific peer.
   *
   * @param {string} remoteUserId
   */
  clearStats(remoteUserId) {
    this._history.delete(remoteUserId);
  }

  /**
   * Clear all stored stats.
   */
  clearAllStats() {
    this._history.clear();
  }

  /**
   * Log a formatted performance summary for a peer to the console.
   * Uses the most recent snapshot if available.
   *
   * @param {string} remoteUserId
   */
  logStatsReport(remoteUserId) {
    const history = this.getStatsHistory(remoteUserId);

    if (history.length === 0) {
      console.log(`[WebRTCStats] No stats available for peer ${remoteUserId}`);
      return;
    }

    const latest = history[history.length - 1];
    const { derived, inboundVideo, inboundAudio, outboundVideo, outboundAudio, candidatePair } = latest;

    console.log(
      `[WebRTCStats] Peer: ${remoteUserId} | ` +
      `Latency: ${derived.latencyMs !== null ? derived.latencyMs + 'ms' : 'n/a'} | ` +
      `Bandwidth: ${derived.bandwidthKbps !== null ? derived.bandwidthKbps + ' kbps' : 'n/a'} | ` +
      `Video loss: ${derived.videoPacketLossPct.toFixed(2)}% | ` +
      `Audio loss: ${derived.audioPacketLossPct.toFixed(2)}%`,
      {
        timestamp: new Date(latest.timestamp).toISOString(),
        inboundVideo,
        inboundAudio,
        outboundVideo,
        outboundAudio,
        candidatePair,
        derived,
        historySize: history.length,
      }
    );
  }

  /**
   * Log performance reports for all tracked peers.
   */
  logAllStatsReports() {
    if (this._history.size === 0) {
      console.log('[WebRTCStats] No stats collected yet.');
      return;
    }
    for (const remoteUserId of this._history.keys()) {
      this.logStatsReport(remoteUserId);
    }
  }
}

export { WebRTCStatsCollector, buildSnapshot, MAX_HISTORY_SIZE };
export default WebRTCStatsCollector;
