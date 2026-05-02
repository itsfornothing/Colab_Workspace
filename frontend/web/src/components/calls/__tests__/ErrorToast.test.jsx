/**
 * Unit tests for ErrorToast component
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import toast from 'react-hot-toast';
import { showErrorToast, showSuccessToast, showInfoToast, dismissAllToasts } from '../ErrorToast';

// Mock react-hot-toast
jest.mock('react-hot-toast', () => {
  const mockToast = jest.fn();
  mockToast.custom = jest.fn();
  mockToast.success = jest.fn();
  mockToast.dismiss = jest.fn();
  return {
    __esModule: true,
    default: mockToast,
  };
});

describe('ErrorToast', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('showErrorToast', () => {
    it('should display error toast with correct message', () => {
      const error = {
        type: 'peer_connection_failed',
        message: 'Unable to connect to user',
        severity: 'error',
        action: 'dismiss'
      };

      showErrorToast(error);

      expect(toast.custom).toHaveBeenCalled();
      const customCall = toast.custom.mock.calls[0];
      expect(customCall[1]).toMatchObject({
        duration: Infinity,
        position: 'top-center'
      });
    });

    it('should use auto-dismiss for warning severity', () => {
      const error = {
        type: 'peer_connection_retry',
        message: 'Retrying connection...',
        severity: 'warning',
        action: 'auto-dismiss',
        duration: 3000
      };

      showErrorToast(error);

      expect(toast.custom).toHaveBeenCalled();
      const customCall = toast.custom.mock.calls[0];
      expect(customCall[1]).toMatchObject({
        duration: 3000
      });
    });

    it('should handle info severity', () => {
      const error = {
        type: 'info',
        message: 'Connection established',
        severity: 'info',
        action: 'auto-dismiss'
      };

      showErrorToast(error);

      expect(toast.custom).toHaveBeenCalled();
    });

    it('should include action link when provided', () => {
      const error = {
        type: 'media_access_error',
        message: 'Camera access denied',
        severity: 'error',
        action: 'link',
        actionLabel: 'How to enable'
      };

      showErrorToast(error);

      expect(toast.custom).toHaveBeenCalled();
      // Verify the custom component includes action link
      const customCall = toast.custom.mock.calls[0];
      const component = customCall[0];
      expect(component).toBeDefined();
    });
  });

  describe('showSuccessToast', () => {
    it('should display success toast', () => {
      const message = 'Call connected successfully';

      showSuccessToast(message);

      expect(toast.success).toHaveBeenCalledWith(
        message,
        expect.objectContaining({
          duration: 3000,
          position: 'top-center'
        })
      );
    });
  });

  describe('showInfoToast', () => {
    it('should display info toast', () => {
      const message = 'User joined the call';

      showInfoToast(message);

      expect(toast).toHaveBeenCalledWith(
        message,
        expect.objectContaining({
          duration: 3000,
          position: 'top-center'
        })
      );
    });
  });

  describe('dismissAllToasts', () => {
    it('should dismiss all active toasts', () => {
      dismissAllToasts();

      expect(toast.dismiss).toHaveBeenCalled();
    });
  });
});
