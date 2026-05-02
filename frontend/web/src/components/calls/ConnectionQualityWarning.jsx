/**
 * ConnectionQualityWarning component
 * Displays warnings when connection quality degrades
 */

import React, { useState, useEffect } from 'react';
import { WifiOff, Wifi, AlertTriangle, X } from 'lucide-react';

/**
 * ConnectionQualityWarning component
 * @param {Object} props
 * @param {Object} props.quality - Connection quality metrics
 * @param {string} props.quality.quality - Quality level (good, fair, poor)
 * @param {number} props.quality.packetLoss - Packet loss percentage
 * @param {number} props.quality.latency - Latency in ms
 * @param {number} props.quality.bandwidth - Bandwidth in kbps
 * @param {string} props.userId - User ID for the connection
 * @param {string} props.userName - User name for display
 * @param {boolean} props.showDetails - Whether to show detailed metrics
 */
const ConnectionQualityWarning = ({
  quality,
  userId,
  userName = 'User',
  showDetails = false
}) => {
  const [isDismissed, setIsDismissed] = useState(false);
  const [showWarning, setShowWarning] = useState(false);

  useEffect(() => {
    // Show warning when quality degrades to poor
    if (quality && quality.quality === 'poor') {
      setShowWarning(true);
      setIsDismissed(false);
    } else if (quality && quality.quality === 'good') {
      // Auto-dismiss when quality improves
      setShowWarning(false);
      setIsDismissed(false);
    }
  }, [quality]);

  if (!showWarning || isDismissed || !quality) {
    return null;
  }

  const getIcon = () => {
    switch (quality.quality) {
      case 'poor':
        return <WifiOff className="w-5 h-5 text-red-500" />;
      case 'fair':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'good':
        return <Wifi className="w-5 h-5 text-green-500" />;
      default:
        return <WifiOff className="w-5 h-5 text-gray-500" />;
    }
  };

  const getBgColor = () => {
    switch (quality.quality) {
      case 'poor':
        return 'bg-red-50 border-red-200';
      case 'fair':
        return 'bg-yellow-50 border-yellow-200';
      case 'good':
        return 'bg-green-50 border-green-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const getTextColor = () => {
    switch (quality.quality) {
      case 'poor':
        return 'text-red-900';
      case 'fair':
        return 'text-yellow-900';
      case 'good':
        return 'text-green-900';
      default:
        return 'text-gray-900';
    }
  };

  const getMessage = () => {
    if (quality.quality === 'poor') {
      return 'Poor connection quality detected. Video quality may be reduced.';
    } else if (quality.quality === 'fair') {
      return 'Connection quality is fair. You may experience some issues.';
    }
    return 'Connection quality is good.';
  };

  return (
    <div className="fixed bottom-24 left-1/2 transform -translate-x-1/2 z-40 max-w-md">
      <div
        className={`${getBgColor()} rounded-lg shadow-lg border px-4 py-3 flex items-start space-x-3 animate-slide-up`}
      >
        <div className="flex-shrink-0 pt-0.5">
          {getIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${getTextColor()}`}>
            {getMessage()}
          </p>
          {showDetails && (
            <div className={`mt-2 text-xs ${getTextColor()} space-y-1`}>
              {quality.packetLoss > 0 && (
                <div className="flex justify-between">
                  <span>Packet Loss:</span>
                  <span className="font-medium">{quality.packetLoss.toFixed(1)}%</span>
                </div>
              )}
              {quality.latency > 0 && (
                <div className="flex justify-between">
                  <span>Latency:</span>
                  <span className="font-medium">{quality.latency}ms</span>
                </div>
              )}
              {quality.bandwidth > 0 && (
                <div className="flex justify-between">
                  <span>Bandwidth:</span>
                  <span className="font-medium">{Math.round(quality.bandwidth)}kbps</span>
                </div>
              )}
            </div>
          )}
        </div>
        <button
          onClick={() => setIsDismissed(true)}
          className={`flex-shrink-0 ${getTextColor()} hover:opacity-70 transition-opacity`}
          aria-label="Dismiss warning"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

/**
 * AudioQualityWarning component
 * Displays warnings when audio quality degrades
 */
export const AudioQualityWarning = ({ audioMetrics, onDismiss }) => {
  const [isDismissed, setIsDismissed] = useState(false);

  useEffect(() => {
    // Reset dismissed state when metrics change significantly
    if (audioMetrics) {
      setIsDismissed(false);
    }
  }, [audioMetrics]);

  if (isDismissed || !audioMetrics) {
    return null;
  }

  const handleDismiss = () => {
    setIsDismissed(true);
    if (onDismiss) {
      onDismiss();
    }
  };

  return (
    <div className="fixed bottom-24 left-1/2 transform -translate-x-1/2 z-40 max-w-md">
      <div className="bg-orange-50 border border-orange-200 rounded-lg shadow-lg px-4 py-3 flex items-start space-x-3 animate-slide-up">
        <div className="flex-shrink-0 pt-0.5">
          <AlertTriangle className="w-5 h-5 text-orange-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-orange-900">
            Audio quality has degraded
          </p>
          <p className="text-xs text-orange-700 mt-1">
            You may experience choppy or distorted audio.
          </p>
        </div>
        <button
          onClick={handleDismiss}
          className="flex-shrink-0 text-orange-900 hover:opacity-70 transition-opacity"
          aria-label="Dismiss warning"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

/**
 * MultipleQualityWarnings component
 * Displays warnings for multiple participants with poor connection
 */
export const MultipleQualityWarnings = ({ qualityMap, onDismiss }) => {
  const [isDismissed, setIsDismissed] = useState(false);

  // Filter for poor quality connections
  const poorConnections = Object.entries(qualityMap || {}).filter(
    ([_, quality]) => quality.quality === 'poor'
  );

  if (isDismissed || poorConnections.length === 0) {
    return null;
  }

  const handleDismiss = () => {
    setIsDismissed(true);
    if (onDismiss) {
      onDismiss();
    }
  };

  return (
    <div className="fixed bottom-24 left-1/2 transform -translate-x-1/2 z-40 max-w-md">
      <div className="bg-red-50 border border-red-200 rounded-lg shadow-lg px-4 py-3 flex items-start space-x-3 animate-slide-up">
        <div className="flex-shrink-0 pt-0.5">
          <WifiOff className="w-5 h-5 text-red-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-red-900">
            Multiple connection issues detected
          </p>
          <p className="text-xs text-red-700 mt-1">
            {poorConnections.length} participant{poorConnections.length > 1 ? 's have' : ' has'} poor connection quality.
          </p>
        </div>
        <button
          onClick={handleDismiss}
          className="flex-shrink-0 text-red-900 hover:opacity-70 transition-opacity"
          aria-label="Dismiss warning"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default ConnectionQualityWarning;
