/**
 * ReconnectingIndicator component
 * Displays a visual indicator when connection issues are detected
 */

import React from 'react';
import { Loader2, WifiOff } from 'lucide-react';

/**
 * ReconnectingIndicator component
 * @param {Object} props
 * @param {boolean} props.isReconnecting - Whether reconnection is in progress
 * @param {string} props.message - Custom message to display
 * @param {number} props.attempt - Current reconnection attempt number
 * @param {number} props.maxAttempts - Maximum number of attempts
 */
const ReconnectingIndicator = ({
  isReconnecting = false,
  message = 'Reconnecting...',
  attempt = 0,
  maxAttempts = 3
}) => {
  if (!isReconnecting) {
    return null;
  }

  return (
    <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg shadow-lg px-4 py-3 flex items-center space-x-3 animate-pulse">
        <Loader2 className="w-5 h-5 text-yellow-600 animate-spin" />
        <div className="flex flex-col">
          <span className="text-sm font-medium text-yellow-900">
            {message}
          </span>
          {attempt > 0 && maxAttempts > 0 && (
            <span className="text-xs text-yellow-700">
              Attempt {attempt} of {maxAttempts}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * ConnectionLostIndicator component
 * Displays when connection is completely lost
 */
export const ConnectionLostIndicator = ({ onRetry }) => {
  return (
    <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
      <div className="bg-red-50 border border-red-200 rounded-lg shadow-lg px-4 py-3 flex items-center space-x-3">
        <WifiOff className="w-5 h-5 text-red-600" />
        <div className="flex flex-col">
          <span className="text-sm font-medium text-red-900">
            Connection Lost
          </span>
          <span className="text-xs text-red-700">
            Unable to connect to the call
          </span>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="ml-4 px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
};

/**
 * PoorConnectionIndicator component
 * Displays when connection quality is poor
 */
export const PoorConnectionIndicator = ({ quality, onDismiss }) => {
  if (!quality || quality.quality !== 'poor') {
    return null;
  }

  return (
    <div className="fixed bottom-20 left-1/2 transform -translate-x-1/2 z-40">
      <div className="bg-orange-50 border border-orange-200 rounded-lg shadow-lg px-4 py-2 flex items-center space-x-3">
        <WifiOff className="w-4 h-4 text-orange-600" />
        <div className="flex flex-col">
          <span className="text-xs font-medium text-orange-900">
            Poor Connection Quality
          </span>
          {quality.packetLoss > 0 && (
            <span className="text-xs text-orange-700">
              Packet loss: {quality.packetLoss.toFixed(1)}%
            </span>
          )}
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="ml-2 text-orange-600 hover:text-orange-800"
          >
            <span className="text-xs">✕</span>
          </button>
        )}
      </div>
    </div>
  );
};

export default ReconnectingIndicator;
