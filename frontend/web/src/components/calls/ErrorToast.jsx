/**
 * ErrorToast component for displaying video call errors
 * Uses react-hot-toast for toast notifications
 */

import React from 'react';
import toast from 'react-hot-toast';
import { AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

/**
 * Show an error toast notification
 * @param {Object} error - Error notification object
 * @param {string} error.type - Error type
 * @param {string} error.message - Error message
 * @param {string} error.severity - Severity level (error, warning, info)
 * @param {string} error.action - Action type (dismiss, auto-dismiss, link)
 * @param {string} error.actionLabel - Label for action button
 * @param {number} error.duration - Duration in ms (for auto-dismiss)
 */
export const showErrorToast = (error) => {
  const {
    type,
    message,
    severity = 'error',
    action = 'dismiss',
    actionLabel,
    duration = 4000
  } = error;

  // Determine icon based on severity
  const getIcon = () => {
    switch (severity) {
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'info':
        return <Info className="w-5 h-5 text-blue-500" />;
      default:
        return <AlertCircle className="w-5 h-5 text-red-500" />;
    }
  };

  // Determine background color based on severity
  const getBgColor = () => {
    switch (severity) {
      case 'error':
        return 'bg-red-50 border-red-200';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200';
      case 'info':
        return 'bg-blue-50 border-blue-200';
      default:
        return 'bg-red-50 border-red-200';
    }
  };

  const toastOptions = {
    duration: action === 'auto-dismiss' ? duration : Infinity,
    position: 'top-center',
    style: {
      maxWidth: '500px',
    }
  };

  toast.custom(
    (t) => (
      <div
        className={`${getBgColor()} ${
          t.visible ? 'animate-enter' : 'animate-leave'
        } max-w-md w-full shadow-lg rounded-lg pointer-events-auto flex border`}
      >
        <div className="flex-1 w-0 p-4">
          <div className="flex items-start">
            <div className="flex-shrink-0 pt-0.5">
              {getIcon()}
            </div>
            <div className="ml-3 flex-1">
              <p className="text-sm font-medium text-gray-900">
                {message}
              </p>
              {actionLabel && action === 'link' && (
                <button
                  onClick={() => {
                    // Open help documentation
                    window.open('https://support.google.com/chrome/answer/2693767', '_blank');
                    toast.dismiss(t.id);
                  }}
                  className="mt-2 text-sm font-medium text-blue-600 hover:text-blue-500"
                >
                  {actionLabel}
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="flex border-l border-gray-200">
          <button
            onClick={() => toast.dismiss(t.id)}
            className="w-full border border-transparent rounded-none rounded-r-lg p-4 flex items-center justify-center text-sm font-medium text-gray-600 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>
    ),
    toastOptions
  );
};

/**
 * Show a success toast notification
 * @param {string} message - Success message
 */
export const showSuccessToast = (message) => {
  toast.success(message, {
    duration: 3000,
    position: 'top-center',
    style: {
      background: '#10B981',
      color: '#fff',
    },
  });
};

/**
 * Show an info toast notification
 * @param {string} message - Info message
 */
export const showInfoToast = (message) => {
  toast(message, {
    duration: 3000,
    position: 'top-center',
    icon: <Info className="w-5 h-5 text-blue-500" />,
  });
};

/**
 * Dismiss all toasts
 */
export const dismissAllToasts = () => {
  toast.dismiss();
};

/**
 * ErrorToast component wrapper for react-hot-toast Toaster
 */
const ErrorToast = () => {
  // This component is not rendered directly
  // It exports utility functions for showing toasts
  return null;
};

export default ErrorToast;
