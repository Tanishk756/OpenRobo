import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RuntimeStudioPage from '../../app/runtime/page';
import * as apiClient from '../../lib/api/client';

describe('RuntimeStudioPage (Milestone 6.1)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Runtime Studio header, probes live backend API, and displays truthful readiness', async () => {
    vi.spyOn(apiClient, 'fetchProviders').mockResolvedValueOnce({
      local_process: { provider_type: 'local_process', status: 'AVAILABLE', details: 'Local colcon ready' },
    });
    vi.spyOn(apiClient, 'fetchRosEnvironment').mockResolvedValueOnce({
      status: 'UNAVAILABLE',
      rclpy_available: false,
      ros2_cli_available: false,
      details: 'ROS not detected on host',
    });
    vi.spyOn(apiClient, 'fetchConnectionInspector').mockResolvedValueOnce({
      status: 'NOT_INSTALLED',
      executables: [],
      licensing_notice: 'GPL-3.0-only boundary',
    });
    vi.spyOn(apiClient, 'fetchSimulators').mockResolvedValueOnce({
      gazebo: { simulator: 'gazebo', installed: false },
    });
    vi.spyOn(apiClient, 'fetchLiveGraph').mockResolvedValueOnce({
      status: 'ROS_RUNTIME_UNAVAILABLE',
      nodes: [],
      topics: [],
    });
    vi.spyOn(apiClient, 'fetchRuntimeSessions').mockResolvedValueOnce([]);

    render(<RuntimeStudioPage />);

    expect(screen.getByText(/OpenRobo/i)).toBeInTheDocument();
    expect(screen.getByText(/Runtime Studio M6.1/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('runtime-status-badge')).toHaveTextContent('RUNTIME_NOT_EXECUTED');
      expect(screen.getByTestId('providers-card')).toBeInTheDocument();
      expect(screen.getByTestId('ros-env-card')).toBeInTheDocument();
      expect(screen.getByTestId('connection-inspector-card')).toBeInTheDocument();
    });
  });

  it('handles backend outage gracefully and displays connection warning', async () => {
    vi.spyOn(apiClient, 'fetchProviders').mockRejectedValueOnce(
      new apiClient.ApiError('Unable to connect to OpenRobo Runtime API.', undefined, true)
    );
    vi.spyOn(apiClient, 'fetchRosEnvironment').mockRejectedValueOnce(
      new apiClient.ApiError('Backend outage', undefined, true)
    );
    vi.spyOn(apiClient, 'fetchConnectionInspector').mockRejectedValueOnce(
      new apiClient.ApiError('Backend outage', undefined, true)
    );
    vi.spyOn(apiClient, 'fetchSimulators').mockRejectedValueOnce(
      new apiClient.ApiError('Backend outage', undefined, true)
    );
    vi.spyOn(apiClient, 'fetchLiveGraph').mockRejectedValueOnce(
      new apiClient.ApiError('Backend outage', undefined, true)
    );
    vi.spyOn(apiClient, 'fetchRuntimeSessions').mockResolvedValueOnce([]);

    render(<RuntimeStudioPage />);

    await waitFor(() => {
      expect(screen.getByTestId('runtime-error-banner')).toBeInTheDocument();
      expect(screen.getByText(/Live Runtime API Unreachable/i)).toBeInTheDocument();
    });
  });

  it('enables explicit Demo Mode and displays DEMO DATA banner and fixtures', async () => {
    vi.spyOn(apiClient, 'fetchProviders').mockResolvedValueOnce({});
    vi.spyOn(apiClient, 'fetchRosEnvironment').mockResolvedValueOnce({
      status: 'UNAVAILABLE',
      rclpy_available: false,
      ros2_cli_available: false,
    });
    vi.spyOn(apiClient, 'fetchConnectionInspector').mockResolvedValueOnce({
      status: 'NOT_INSTALLED',
      executables: [],
      licensing_notice: 'GPL-3.0-only boundary',
    });
    vi.spyOn(apiClient, 'fetchSimulators').mockResolvedValueOnce({});
    vi.spyOn(apiClient, 'fetchLiveGraph').mockResolvedValueOnce({ status: 'OK', nodes: [], topics: [] });
    vi.spyOn(apiClient, 'fetchRuntimeSessions').mockResolvedValueOnce([]);

    render(<RuntimeStudioPage />);

    const demoToggle = screen.getByTestId('toggle-demo-mode');
    fireEvent.click(demoToggle);

    await waitFor(() => {
      expect(screen.getByTestId('demo-data-banner')).toBeInTheDocument();
      expect(screen.getByTestId('runtime-status-badge')).toHaveTextContent('DEMO_DATA');
      expect(screen.getByTestId('topic-row-scan')).toBeInTheDocument();
    });
  });

  it('switches to nodes tab in demo mode and verifies node cards', async () => {
    render(<RuntimeStudioPage />);

    // Enable demo mode
    const demoToggle = screen.getByTestId('toggle-demo-mode');
    fireEvent.click(demoToggle);

    await waitFor(() => {
      expect(screen.getByTestId('tab-nodes')).toBeInTheDocument();
    });

    const nodesTab = screen.getByTestId('tab-nodes');
    fireEvent.click(nodesTab);

    expect(screen.getByTestId('node-card-slam_toolbox')).toBeInTheDocument();
    expect(screen.getByTestId('node-card-rplidar_node')).toBeInTheDocument();
  });
});
