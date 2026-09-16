import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ResourcesPage from '../../app/resources/page';
import * as apiClient from '../../lib/api/client';
import { Resource } from '../../lib/api/types';

const MOCK_RESOURCES: Resource[] = [
  {
    id: 'ros-controls/ros2_control',
    name: 'ros2_control Framework',
    version: '4.15.0',
    type: 'ros_package',
    summary: 'Real-time robot control architecture for ROS 2',
    spdx_license_id: 'Apache-2.0',
    robotics_domains: ['control', 'manipulation'],
    capabilities: ['real-time-control', 'hardware-interface'],
    platforms: {
      operating_systems: ['Ubuntu 24.04'],
      ros_versions: ['Jazzy', 'Humble'],
    },
    evidence_level: 'ci_verified',
  },
  {
    id: 'robotis/turtlebot3',
    name: 'TurtleBot3 Platform',
    version: '2.1.5',
    type: 'robot',
    summary: 'Standard educational mobile robotics platform',
    spdx_license_id: 'Apache-2.0',
    robotics_domains: ['amr', 'education'],
    capabilities: ['differential-drive'],
    platforms: {
      operating_systems: ['Ubuntu 24.04'],
      ros_versions: ['Jazzy'],
    },
    evidence_level: 'ci_verified',
  },
];

describe('ResourcesPage (Resource Explorer)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading state then displays resource cards', async () => {
    vi.spyOn(apiClient, 'fetchResources').mockResolvedValueOnce({
      items: MOCK_RESOURCES,
      total: 2,
      limit: 50,
      offset: 0,
    });

    render(<ResourcesPage />);
    expect(screen.getByTestId('loading-state')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('ros2_control Framework')).toBeInTheDocument();
      expect(screen.getByText('TurtleBot3 Platform')).toBeInTheDocument();
    });

    expect(screen.getByTestId('resource-card-ros-controls/ros2_control')).toBeInTheDocument();
  });

  it('displays empty state when no resources match', async () => {
    vi.spyOn(apiClient, 'fetchResources').mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText(/No Robotics Resources Found/i)).toBeInTheDocument();
    });
  });

  it('displays API error banner when backend is unreachable', async () => {
    vi.spyOn(apiClient, 'fetchResources').mockRejectedValueOnce(
      new apiClient.ApiError('Backend unreachable', undefined, true)
    );

    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getByTestId('api-error-state')).toBeInTheDocument();
      expect(screen.getByText(/Backend API Service Unreachable/i)).toBeInTheDocument();
    });
  });

  it('opens detail drawer when a resource card is clicked and closes it', async () => {
    vi.spyOn(apiClient, 'fetchResources').mockResolvedValueOnce({
      items: MOCK_RESOURCES,
      total: 2,
      limit: 50,
      offset: 0,
    });

    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getByText('ros2_control Framework')).toBeInTheDocument();
    });

    // Click card
    fireEvent.click(screen.getByTestId('resource-card-ros-controls/ros2_control'));

    // Verify detail drawer opened
    await waitFor(() => {
      expect(screen.getByTestId('detail-drawer')).toBeInTheDocument();
      expect(screen.getByText(/Platform Matrix/i)).toBeInTheDocument();
      expect(screen.getByText(/Robotics Capabilities/i)).toBeInTheDocument();
    });

    // Click close button
    fireEvent.click(screen.getByTestId('close-drawer'));

    await waitFor(() => {
      expect(screen.queryByTestId('detail-drawer')).not.toBeInTheDocument();
    });
  });

  it('triggers search query filtering when typing in search input', async () => {
    const fetchSpy = vi.spyOn(apiClient, 'fetchResources').mockResolvedValue({
      items: [MOCK_RESOURCES[0]],
      total: 1,
      limit: 50,
      offset: 0,
    });

    render(<ResourcesPage />);

    const searchInput = screen.getByTestId('search-input');
    fireEvent.change(searchInput, { target: { value: 'control' } });

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(expect.objectContaining({ q: 'control' }));
    });
  });
});
