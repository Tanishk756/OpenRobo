import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import RuntimeStudioPage from '../../app/runtime/page';

describe('RuntimeStudioPage (Milestone 6)', () => {
  it('renders Runtime Studio header, status badge, and core cards', () => {
    render(<RuntimeStudioPage />);

    expect(screen.getByText(/OpenRobo/i)).toBeInTheDocument();
    expect(screen.getByText(/Runtime Studio M6/i)).toBeInTheDocument();
    expect(screen.getByTestId('runtime-status-badge')).toHaveTextContent('BUILD_VERIFIED');
    expect(screen.getByTestId('providers-card')).toBeInTheDocument();
    expect(screen.getByTestId('connection-inspector-card')).toBeInTheDocument();
    expect(screen.getByTestId('simulators-card')).toBeInTheDocument();
  });

  it('displays Connection Inspector licensing boundary notice', () => {
    render(<RuntimeStudioPage />);

    expect(screen.getByText(/GPL-3.0-only tool boundary/i)).toBeInTheDocument();
    expect(screen.getByText(/NOT_INSTALLED/i)).toBeInTheDocument();
  });

  it('switches between ROS Graph connections and Node Liveness tabs', () => {
    render(<RuntimeStudioPage />);

    expect(screen.getByText(/Active Topic Connections & QoS Evaluation/i)).toBeInTheDocument();
    expect(screen.getByTestId('topic-row-scan')).toBeInTheDocument();

    // Switch to Nodes tab
    const nodesTab = screen.getByTestId('tab-nodes');
    fireEvent.click(nodesTab);

    expect(screen.getByTestId('node-card-slam_toolbox')).toBeInTheDocument();
    expect(screen.getByTestId('node-card-rplidar_node')).toBeInTheDocument();
  });

  it('updates topic inspector panel when clicking a topic row', () => {
    render(<RuntimeStudioPage />);

    const mapRow = screen.getByTestId('topic-row-map');
    fireEvent.click(mapRow);

    expect(screen.getAllByText('/map').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('nav_msgs/msg/OccupancyGrid').length).toBeGreaterThanOrEqual(1);
  });
});
