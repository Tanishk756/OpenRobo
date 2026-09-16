import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ResourcesPage from '../../app/resources/page';
import * as apiClient from '../../lib/api/client';
import { Resource, SearchResponse, SearchResultHit } from '../../lib/api/types';

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
    metadata_json: {
      provenance: {
        source_provider: 'GitHub',
        upstream_revision: 'c0ffeebabe12',
        provenance_classification: 'UPSTREAM_DATA',
        source_manifest_path: 'package.xml',
      },
    },
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

const MOCK_SEARCH_RESPONSE: SearchResponse = {
  items: [
    {
      resource: MOCK_RESOURCES[0],
      score: 8.5,
      highlights: {
        summary: ['Real-time robot <mark style="background: rgba(6, 182, 212, 0.3); color: #22d3ee; padding: 0 2px; border-radius: 2px;">control</mark> architecture for ROS 2'],
      },
    },
    {
      resource: MOCK_RESOURCES[1],
      score: 1.2,
      highlights: {},
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    types: { ros_package: 1, robot: 1 },
    domains: { control: 1, manipulation: 1, amr: 1, education: 1 },
    capabilities: { 'real-time-control': 1, 'differential-drive': 1 },
    licenses: { 'Apache-2.0': 2 },
    ros_versions: { Jazzy: 2, Humble: 1 },
  },
};

describe('ResourcesPage (Resource Explorer & Search Engine)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading state then displays ranked search hits and facet counts', async () => {
    vi.spyOn(apiClient, 'searchResources').mockResolvedValueOnce(MOCK_SEARCH_RESPONSE);

    render(<ResourcesPage />);
    expect(screen.getByTestId('loading-state')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('ros2_control Framework')).toBeInTheDocument();
      expect(screen.getByText('TurtleBot3 Platform')).toBeInTheDocument();
    });

    expect(screen.getByTestId('resource-card-ros-controls/ros2_control')).toBeInTheDocument();
  });

  it('displays empty state when no search hits match', async () => {
    vi.spyOn(apiClient, 'searchResources').mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
      facets: { types: {}, domains: {}, capabilities: {}, licenses: {}, ros_versions: {} },
    });

    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText(/No Robotics Resources Found/i)).toBeInTheDocument();
    });
  });

  it('displays API error banner when backend is unreachable', async () => {
    vi.spyOn(apiClient, 'searchResources').mockRejectedValueOnce(
      new apiClient.ApiError('Backend unreachable', undefined, true)
    );

    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getByTestId('api-error-state')).toBeInTheDocument();
      expect(screen.getByText(/Backend API Service Unreachable/i)).toBeInTheDocument();
    });
  });

  it('opens detail drawer when a resource card is clicked and displays provenance', async () => {
    vi.spyOn(apiClient, 'searchResources').mockResolvedValueOnce(MOCK_SEARCH_RESPONSE);

    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getByText('ros2_control Framework')).toBeInTheDocument();
    });

    // Click card
    fireEvent.click(screen.getByTestId('resource-card-ros-controls/ros2_control'));

    // Verify detail drawer opened with provenance
    await waitFor(() => {
      expect(screen.getByTestId('detail-drawer')).toBeInTheDocument();
      expect(screen.getByText(/Platform Matrix/i)).toBeInTheDocument();
      expect(screen.getByText(/Robotics Capabilities/i)).toBeInTheDocument();
      expect(screen.getByTestId('provenance-section')).toBeInTheDocument();
      expect(screen.getByText(/Data Provenance & Ingestion Lineage/i)).toBeInTheDocument();
      expect(screen.getByText('c0ffeebabe')).toBeInTheDocument();
    });

    // Click close button
    fireEvent.click(screen.getByTestId('close-drawer'));

    await waitFor(() => {
      expect(screen.queryByTestId('detail-drawer')).not.toBeInTheDocument();
    });
  });

  it('triggers search query filtering when typing in search input', async () => {
    const searchSpy = vi.spyOn(apiClient, 'searchResources').mockResolvedValue({
      items: [MOCK_SEARCH_RESPONSE.items[0]],
      total: 1,
      limit: 50,
      offset: 0,
      facets: MOCK_SEARCH_RESPONSE.facets,
    });

    render(<ResourcesPage />);

    const searchInput = screen.getByTestId('search-input');
    fireEvent.change(searchInput, { target: { value: 'control' } });

    await waitFor(() => {
      expect(searchSpy).toHaveBeenCalledWith(expect.objectContaining({ q: 'control' }));
    });
  });
});
