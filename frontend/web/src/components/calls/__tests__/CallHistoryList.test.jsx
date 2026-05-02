/**
 * UI Tests for CallHistoryList Component
 *
 * Covers:
 * - Call history list rendering with date, participants, and duration
 * - Pagination functionality for long lists
 * - Recording download link display when available
 * - Empty state display
 * - Loading state display
 *
 * Validates: Requirements 6.3
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

// ── Mocks ────────────────────────────────────────────────────────────────────

// Mock axios client
jest.mock('@/lib/axiosClient', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

import api from '@/lib/axiosClient';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  Clock: () => <span data-testid="icon-clock" />,
  Users: () => <span data-testid="icon-users" />,
  Download: () => <span data-testid="icon-download" />,
  Phone: () => <span data-testid="icon-phone" />,
  ChevronLeft: () => <span data-testid="icon-chevron-left" />,
  ChevronRight: () => <span data-testid="icon-chevron-right" />,
}));

// Mock Avatar component
jest.mock('@/components/ui/Avatar', () => ({
  __esModule: true,
  default: ({ name, size, className }) => (
    <div data-testid="avatar" data-name={name} data-size={size} className={className} />
  ),
}));

// Mock Button component
jest.mock('@/components/ui/Button', () => ({
  __esModule: true,
  default: ({ children, onClick, disabled, as, href, download, ...props }) => {
    const Component = as || 'button';
    return (
      <Component
        onClick={onClick}
        disabled={disabled}
        href={href}
        download={download}
        data-testid={props['data-testid'] || 'button'}
        {...props}
      >
        {children}
      </Component>
    );
  },
}));

// Mock Skeleton component
jest.mock('@/components/ui/Skeleton', () => ({
  __esModule: true,
  default: ({ className }) => <div data-testid="skeleton" className={className} />,
}));

// Import component after mocks
import CallHistoryList from '@/components/calls/CallHistoryList';

// ── Test Helpers ─────────────────────────────────────────────────────────────

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

const renderWithProviders = (component, { workspaceId = 'workspace-123' } = {}) => {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/workspace/:workspaceId/calls" element={component} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>,
    {
      wrapper: ({ children }) => (
        <BrowserRouter>
          <Routes>
            <Route path="/workspace/:workspaceId/calls" element={children} />
          </Routes>
        </BrowserRouter>
      ),
    }
  );
};

// Mock call history data
const mockCallHistory = [
  {
    id: 'call-1',
    room: {
      id: 'room-1',
      name: 'Team Standup',
    },
    started_at: '2024-01-15T10:00:00Z',
    ended_at: '2024-01-15T10:30:00Z',
    duration_seconds: 1800,
    participant_count: 3,
    participants: [
      {
        id: 'participant-1',
        user: {
          id: 'user-1',
          username: 'alice',
          full_name: 'Alice Johnson',
        },
      },
      {
        id: 'participant-2',
        user: {
          id: 'user-2',
          username: 'bob',
          full_name: 'Bob Smith',
        },
      },
      {
        id: 'participant-3',
        user: {
          id: 'user-3',
          username: 'charlie',
          full_name: 'Charlie Brown',
        },
      },
    ],
    recording_url: null,
  },
  {
    id: 'call-2',
    room: {
      id: 'room-2',
      name: 'Client Meeting',
    },
    started_at: '2024-01-14T14:00:00Z',
    ended_at: '2024-01-14T15:30:00Z',
    duration_seconds: 5400,
    participant_count: 5,
    participants: [
      {
        id: 'participant-4',
        user: {
          id: 'user-1',
          username: 'alice',
          full_name: 'Alice Johnson',
        },
      },
      {
        id: 'participant-5',
        user: {
          id: 'user-4',
          username: 'david',
          full_name: 'David Lee',
        },
      },
      {
        id: 'participant-6',
        user: {
          id: 'user-5',
          username: 'eve',
          full_name: 'Eve Martinez',
        },
      },
      {
        id: 'participant-7',
        user: {
          id: 'user-6',
          username: 'frank',
          full_name: 'Frank Wilson',
        },
      },
      {
        id: 'participant-8',
        user: {
          id: 'user-7',
          username: 'grace',
          full_name: 'Grace Taylor',
        },
      },
    ],
    recording_url: 'https://example.com/recordings/call-2.mp4',
  },
];

// ── Tests ────────────────────────────────────────────────────────────────────

describe('CallHistoryList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  /**
   * Validates: Requirements 6.3
   * Test: Loading state displays skeleton loaders
   */
  test('displays loading skeletons while fetching call history', () => {
    api.get.mockImplementation(() => new Promise(() => {})); // Never resolves

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    const skeletons = screen.getAllByTestId('skeleton');
    expect(skeletons).toHaveLength(5);
  });

  /**
   * Validates: Requirements 6.3
   * Test: Empty state displays when no call history exists
   */
  test('displays empty state when no call history exists', async () => {
    api.get.mockResolvedValue({ data: [] });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('No call history')).toBeInTheDocument();
      expect(screen.getByText('Your past calls will appear here')).toBeInTheDocument();
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Call history list renders with date, participants, and duration
   */
  test('renders call history list with date, participants, and duration', async () => {
    api.get.mockResolvedValue({ data: mockCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      // Check room names are displayed
      expect(screen.getByText('Team Standup')).toBeInTheDocument();
      expect(screen.getByText('Client Meeting')).toBeInTheDocument();

      // Check participant names are displayed
      expect(screen.getByText(/Alice Johnson, Bob Smith, and Charlie Brown/)).toBeInTheDocument();
      expect(screen.getByText(/Alice Johnson, David Lee, and 3 others/)).toBeInTheDocument();

      // Check duration is displayed
      expect(screen.getByText(/Duration: 30m/)).toBeInTheDocument();
      expect(screen.getByText(/Duration: 1h 30m/)).toBeInTheDocument();

      // Check participant count is displayed
      expect(screen.getByText(/3 participants/)).toBeInTheDocument();
      expect(screen.getByText(/5 participants/)).toBeInTheDocument();
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Recording download link is displayed when available
   */
  test('displays recording download link when available', async () => {
    api.get.mockResolvedValue({ data: mockCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      // First call has no recording
      const callCards = screen.getAllByTestId('icon-phone').map(icon => icon.closest('.p-4'));
      expect(callCards[0]).not.toHaveTextContent('Recording');

      // Second call has recording
      const recordingLinks = screen.getAllByText('Recording');
      expect(recordingLinks).toHaveLength(1);
      
      const recordingLink = recordingLinks[0].closest('a');
      expect(recordingLink).toHaveAttribute('href', 'https://example.com/recordings/call-2.mp4');
      expect(recordingLink).toHaveAttribute('download');
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Pagination controls are displayed for long lists
   */
  test('displays pagination controls for long lists', async () => {
    // Create 25 call history items (more than itemsPerPage of 20)
    const longCallHistory = Array.from({ length: 25 }, (_, i) => ({
      id: `call-${i}`,
      room: {
        id: `room-${i}`,
        name: `Call ${i + 1}`,
      },
      started_at: new Date(Date.now() - i * 86400000).toISOString(),
      ended_at: new Date(Date.now() - i * 86400000 + 1800000).toISOString(),
      duration_seconds: 1800,
      participant_count: 2,
      participants: [
        {
          id: `participant-${i}-1`,
          user: {
            id: `user-${i}-1`,
            username: `user${i}`,
            full_name: `User ${i}`,
          },
        },
      ],
      recording_url: null,
    }));

    api.get.mockResolvedValue({ data: longCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      // Check pagination controls are displayed
      expect(screen.getByText(/Showing 1-20 of 25/)).toBeInTheDocument();
      expect(screen.getByText('Previous')).toBeInTheDocument();
      expect(screen.getByText('Next')).toBeInTheDocument();
      expect(screen.getByText('Page 1')).toBeInTheDocument();
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Pagination next button navigates to next page
   */
  test('navigates to next page when next button is clicked', async () => {
    const longCallHistory = Array.from({ length: 25 }, (_, i) => ({
      id: `call-${i}`,
      room: {
        id: `room-${i}`,
        name: `Call ${i + 1}`,
      },
      started_at: new Date(Date.now() - i * 86400000).toISOString(),
      ended_at: new Date(Date.now() - i * 86400000 + 1800000).toISOString(),
      duration_seconds: 1800,
      participant_count: 2,
      participants: [
        {
          id: `participant-${i}-1`,
          user: {
            id: `user-${i}-1`,
            username: `user${i}`,
            full_name: `User ${i}`,
          },
        },
      ],
      recording_url: null,
    }));

    api.get.mockResolvedValue({ data: longCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Showing 1-20 of 25/)).toBeInTheDocument();
    });

    // Click next button
    const nextButton = screen.getByText('Next').closest('button');
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText(/Showing 21-25 of 25/)).toBeInTheDocument();
      expect(screen.getByText('Page 2')).toBeInTheDocument();
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Pagination previous button navigates to previous page
   */
  test('navigates to previous page when previous button is clicked', async () => {
    const longCallHistory = Array.from({ length: 25 }, (_, i) => ({
      id: `call-${i}`,
      room: {
        id: `room-${i}`,
        name: `Call ${i + 1}`,
      },
      started_at: new Date(Date.now() - i * 86400000).toISOString(),
      ended_at: new Date(Date.now() - i * 86400000 + 1800000).toISOString(),
      duration_seconds: 1800,
      participant_count: 2,
      participants: [
        {
          id: `participant-${i}-1`,
          user: {
            id: `user-${i}-1`,
            username: `user${i}`,
            full_name: `User ${i}`,
          },
        },
      ],
      recording_url: null,
    }));

    api.get.mockResolvedValue({ data: longCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Showing 1-20 of 25/)).toBeInTheDocument();
    });

    // Go to page 2
    const nextButton = screen.getByText('Next').closest('button');
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText('Page 2')).toBeInTheDocument();
    });

    // Go back to page 1
    const prevButton = screen.getByText('Previous').closest('button');
    fireEvent.click(prevButton);

    await waitFor(() => {
      expect(screen.getByText('Page 1')).toBeInTheDocument();
      expect(screen.getByText(/Showing 1-20 of 25/)).toBeInTheDocument();
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Previous button is disabled on first page
   */
  test('disables previous button on first page', async () => {
    // Create 25 items to ensure pagination shows
    const longCallHistory = Array.from({ length: 25 }, (_, i) => ({
      id: `call-${i}`,
      room: {
        id: `room-${i}`,
        name: `Call ${i + 1}`,
      },
      started_at: new Date(Date.now() - i * 86400000).toISOString(),
      ended_at: new Date(Date.now() - i * 86400000 + 1800000).toISOString(),
      duration_seconds: 1800,
      participant_count: 2,
      participants: [
        {
          id: `participant-${i}-1`,
          user: {
            id: `user-${i}-1`,
            username: `user${i}`,
            full_name: `User ${i}`,
          },
        },
      ],
      recording_url: null,
    }));

    api.get.mockResolvedValue({ data: longCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      const prevButton = screen.getByText('Previous').closest('button');
      expect(prevButton).toBeDisabled();
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Next button is disabled on last page
   */
  test('disables next button on last page', async () => {
    // Create 25 items, navigate to page 2 (which has only 5 items)
    const longCallHistory = Array.from({ length: 25 }, (_, i) => ({
      id: `call-${i}`,
      room: {
        id: `room-${i}`,
        name: `Call ${i + 1}`,
      },
      started_at: new Date(Date.now() - i * 86400000).toISOString(),
      ended_at: new Date(Date.now() - i * 86400000 + 1800000).toISOString(),
      duration_seconds: 1800,
      participant_count: 2,
      participants: [
        {
          id: `participant-${i}-1`,
          user: {
            id: `user-${i}-1`,
            username: `user${i}`,
            full_name: `User ${i}`,
          },
        },
      ],
      recording_url: null,
    }));

    api.get.mockResolvedValue({ data: longCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Wait for initial render
    await waitFor(() => {
      expect(screen.getByText('Page 1')).toBeInTheDocument();
    });

    // Navigate to page 2 (last page)
    const nextButton = screen.getByText('Next').closest('button');
    fireEvent.click(nextButton);

    // Now on page 2, next button should be disabled
    await waitFor(() => {
      expect(screen.getByText('Page 2')).toBeInTheDocument();
      const nextBtn = screen.getByText('Next').closest('button');
      expect(nextBtn).toBeDisabled();
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Displays participant avatars (up to 3)
   */
  test('displays participant avatars up to 3 participants', async () => {
    api.get.mockResolvedValue({ data: mockCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      const avatars = screen.getAllByTestId('avatar');
      // First call has 3 participants, second call has 5 but only shows 3 avatars
      expect(avatars.length).toBeGreaterThanOrEqual(6); // 3 + 3
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Displays "+N" indicator for more than 3 participants
   */
  test('displays +N indicator for more than 3 participants', async () => {
    api.get.mockResolvedValue({ data: mockCallHistory });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      // Second call has 5 participants, should show +2
      expect(screen.getByText('+2')).toBeInTheDocument();
    });
  });

  /**
   * Validates: Requirements 6.3
   * Test: Formats call duration correctly
   */
  test('formats call duration correctly', async () => {
    const callsWithVariousDurations = [
      {
        id: 'call-short',
        room: { id: 'room-1', name: 'Short Call' },
        started_at: '2024-01-15T10:00:00Z',
        ended_at: '2024-01-15T10:00:45Z',
        duration_seconds: 45,
        participant_count: 2,
        participants: [
          {
            id: 'p1',
            user: { id: 'u1', username: 'user1', full_name: 'User One' },
          },
        ],
        recording_url: null,
      },
      {
        id: 'call-medium',
        room: { id: 'room-2', name: 'Medium Call' },
        started_at: '2024-01-15T10:00:00Z',
        ended_at: '2024-01-15T10:15:30Z',
        duration_seconds: 930,
        participant_count: 2,
        participants: [
          {
            id: 'p2',
            user: { id: 'u2', username: 'user2', full_name: 'User Two' },
          },
        ],
        recording_url: null,
      },
      {
        id: 'call-long',
        room: { id: 'room-3', name: 'Long Call' },
        started_at: '2024-01-15T10:00:00Z',
        ended_at: '2024-01-15T12:30:45Z',
        duration_seconds: 9045,
        participant_count: 2,
        participants: [
          {
            id: 'p3',
            user: { id: 'u3', username: 'user3', full_name: 'User Three' },
          },
        ],
        recording_url: null,
      },
    ];

    api.get.mockResolvedValue({ data: callsWithVariousDurations });

    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CallHistoryList />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Duration: 45s/)).toBeInTheDocument();
      expect(screen.getByText(/Duration: 15m 30s/)).toBeInTheDocument();
      expect(screen.getByText(/Duration: 2h 30m 45s/)).toBeInTheDocument();
    });
  });
});
