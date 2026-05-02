/**
 * Unit tests for ReconnectingIndicator component
 */

import { render, screen, fireEvent } from '@testing-library/react';
import ReconnectingIndicator, {
  ConnectionLostIndicator,
  PoorConnectionIndicator
} from '../ReconnectingIndicator';

describe('ReconnectingIndicator', () => {
  it('should not render when isReconnecting is false', () => {
    const { container } = render(
      <ReconnectingIndicator isReconnecting={false} />
    );

    expect(container.firstChild).toBeNull();
  });

  it('should render when isReconnecting is true', () => {
    render(<ReconnectingIndicator isReconnecting={true} />);

    expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
  });

  it('should display custom message', () => {
    const customMessage = 'Attempting to reconnect to server...';
    render(
      <ReconnectingIndicator
        isReconnecting={true}
        message={customMessage}
      />
    );

    expect(screen.getByText(customMessage)).toBeInTheDocument();
  });

  it('should display attempt count when provided', () => {
    render(
      <ReconnectingIndicator
        isReconnecting={true}
        attempt={2}
        maxAttempts={3}
      />
    );

    expect(screen.getByText('Attempt 2 of 3')).toBeInTheDocument();
  });

  it('should not display attempt count when attempt is 0', () => {
    render(
      <ReconnectingIndicator
        isReconnecting={true}
        attempt={0}
        maxAttempts={3}
      />
    );

    expect(screen.queryByText(/Attempt/)).not.toBeInTheDocument();
  });
});

describe('ConnectionLostIndicator', () => {
  it('should render connection lost message', () => {
    render(<ConnectionLostIndicator />);

    expect(screen.getByText('Connection Lost')).toBeInTheDocument();
    expect(screen.getByText('Unable to connect to the call')).toBeInTheDocument();
  });

  it('should render retry button when onRetry is provided', () => {
    const mockOnRetry = jest.fn();
    render(<ConnectionLostIndicator onRetry={mockOnRetry} />);

    const retryButton = screen.getByRole('button', { name: /retry/i });
    expect(retryButton).toBeInTheDocument();
  });

  it('should call onRetry when retry button is clicked', () => {
    const mockOnRetry = jest.fn();
    render(<ConnectionLostIndicator onRetry={mockOnRetry} />);

    const retryButton = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryButton);

    expect(mockOnRetry).toHaveBeenCalledTimes(1);
  });

  it('should not render retry button when onRetry is not provided', () => {
    render(<ConnectionLostIndicator />);

    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });
});

describe('PoorConnectionIndicator', () => {
  it('should not render when quality is null', () => {
    const { container } = render(
      <PoorConnectionIndicator quality={null} />
    );

    expect(container.firstChild).toBeNull();
  });

  it('should not render when quality is good', () => {
    const quality = {
      quality: 'good',
      packetLoss: 0,
      latency: 50
    };

    const { container } = render(
      <PoorConnectionIndicator quality={quality} />
    );

    expect(container.firstChild).toBeNull();
  });

  it('should render when quality is poor', () => {
    const quality = {
      quality: 'poor',
      packetLoss: 10,
      latency: 350
    };

    render(<PoorConnectionIndicator quality={quality} />);

    expect(screen.getByText('Poor Connection Quality')).toBeInTheDocument();
  });

  it('should display packet loss when available', () => {
    const quality = {
      quality: 'poor',
      packetLoss: 12.5,
      latency: 350
    };

    render(<PoorConnectionIndicator quality={quality} />);

    expect(screen.getByText('Packet loss: 12.5%')).toBeInTheDocument();
  });

  it('should not display packet loss when it is 0', () => {
    const quality = {
      quality: 'poor',
      packetLoss: 0,
      latency: 350
    };

    render(<PoorConnectionIndicator quality={quality} />);

    expect(screen.queryByText(/Packet loss/)).not.toBeInTheDocument();
  });

  it('should call onDismiss when dismiss button is clicked', () => {
    const mockOnDismiss = jest.fn();
    const quality = {
      quality: 'poor',
      packetLoss: 10,
      latency: 350
    };

    render(
      <PoorConnectionIndicator
        quality={quality}
        onDismiss={mockOnDismiss}
      />
    );

    const dismissButton = screen.getByRole('button');
    fireEvent.click(dismissButton);

    expect(mockOnDismiss).toHaveBeenCalledTimes(1);
  });
});
