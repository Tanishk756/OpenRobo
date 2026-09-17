import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import StackBuilderPage from '../../app/stack-builder/page';
import * as apiClient from '../../lib/api/client';
import { Resource, StackTemplate, StackValidationResponse } from '../../lib/api/types';

const MOCK_RESOURCES: Resource[] = [
  {
    id: 'ros-navigation/nav2',
    name: 'Nav2 Framework',
    version: '1.3.0',
    type: 'ros_package',
    summary: 'Autonomous Navigation Framework for ROS 2',
    spdx_license_id: 'Apache-2.0',
    robotics_domains: ['navigation', 'amr'],
  },
  {
    id: 'stevemacenski/slam_toolbox',
    name: 'SLAM Toolbox',
    version: '2.7.4',
    type: 'ros_package',
    summary: '2D SLAM and Spatial Mapping',
    spdx_license_id: 'LGPL-2.1',
    robotics_domains: ['mapping', 'slam'],
  },
];

const MOCK_TEMPLATES: StackTemplate[] = [
  {
    id: 'mobile_robot_navigation',
    name: 'turtlebot3_nav2_jazzy',
    title: 'Mobile Robot Navigation',
    description: 'Standard autonomous mobile robot navigation with Nav2',
    robot_domain: 'mobile_robotics',
    robot_type: 'differential_drive',
    target_os: 'ubuntu_24_04',
    target_arch: 'x86_64',
    target_ros_distro: 'jazzy',
    components: [
      { resource_id: 'ros-navigation/nav2', version: '1.3.0', category: 'navigation' },
      { resource_id: 'stevemacenski/slam_toolbox', version: '2.7.4', category: 'mapping' },
    ],
  },
];

const MOCK_VALIDATION: StackValidationResponse = {
  status: 'compatible',
  total_components: 2,
  verified_compatible_count: 2,
  conditional_count: 0,
  incompatible_count: 0,
  unknown_count: 0,
  missing_dependencies_count: 0,
  version_conflicts_count: 0,
  cycles_count: 0,
  compatibility_result: {
    status: 'compatible',
    resource_ids: ['ros-navigation/nav2', 'stevemacenski/slam_toolbox'],
    rule_evaluations: [
      {
        rule_name: 'ROS Distribution Rule',
        status: 'compatible',
        message: 'All components support ROS 2 Jazzy',
        evidence_level: 'inferred',
      },
    ],
    conflicts: [],
    warnings: [],
    missing_requirements: [],
    dependency_paths: [],
    evidence_level: 'inferred',
    evaluated_at: '2026-09-17T12:00:00Z',
  },
  evaluated_at: '2026-09-17T12:00:00Z',
};

describe('StackBuilderPage (Interactive Robotics Stack Builder)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders workspace with top controls, empty state, and loads resource library', async () => {
    vi.spyOn(apiClient, 'fetchResources').mockResolvedValueOnce({
      items: MOCK_RESOURCES,
      total: 2,
      limit: 50,
      offset: 0,
    });
    vi.spyOn(apiClient, 'fetchStackTemplates').mockResolvedValueOnce(MOCK_TEMPLATES);

    render(<StackBuilderPage />);

    expect(screen.getByPlaceholderText('Stack Identifier')).toBeInTheDocument();
    expect(screen.getByText(/Your Robotics Stack is Empty/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Nav2 Framework')).toBeInTheDocument();
      expect(screen.getByText('SLAM Toolbox')).toBeInTheDocument();
    });
  });

  it('adds component from Library to Stack composition and triggers live validation', async () => {
    vi.spyOn(apiClient, 'fetchResources').mockResolvedValueOnce({
      items: MOCK_RESOURCES,
      total: 2,
      limit: 50,
      offset: 0,
    });
    vi.spyOn(apiClient, 'fetchStackTemplates').mockResolvedValueOnce(MOCK_TEMPLATES);
    const validateSpy = vi.spyOn(apiClient, 'validateAdhocStack').mockResolvedValue(MOCK_VALIDATION);

    render(<StackBuilderPage />);

    await waitFor(() => {
      expect(screen.getByText('Nav2 Framework')).toBeInTheDocument();
    });

    const addButtons = screen.getAllByText('+ Add');
    fireEvent.click(addButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Navigation & Planning')).toBeInTheDocument();
      expect(validateSpy).toHaveBeenCalled();
    });
  });

  it('loads starter template into stack composition', async () => {
    vi.spyOn(apiClient, 'fetchResources').mockResolvedValueOnce({
      items: MOCK_RESOURCES,
      total: 2,
      limit: 50,
      offset: 0,
    });
    vi.spyOn(apiClient, 'fetchStackTemplates').mockResolvedValueOnce(MOCK_TEMPLATES);
    vi.spyOn(apiClient, 'validateAdhocStack').mockResolvedValue(MOCK_VALIDATION);

    render(<StackBuilderPage />);

    await waitFor(() => {
      expect(screen.getByText('Load Starter Template...')).toBeInTheDocument();
    });

    const select = screen.getByDisplayValue('Load Starter Template...');
    fireEvent.change(select, { target: { value: 'mobile_robot_navigation' } });

    await waitFor(() => {
      expect(screen.getByDisplayValue('turtlebot3_nav2_jazzy')).toBeInTheDocument();
      expect(screen.getByText('Navigation & Planning')).toBeInTheDocument();
      expect(screen.getByText('Localization & SLAM')).toBeInTheDocument();
    });
  });
});
