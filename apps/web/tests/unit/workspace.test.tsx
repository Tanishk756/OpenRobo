import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WorkspaceModal } from '../../app/stack-builder/WorkspaceModal';
import * as apiClient from '../../lib/api/client';
import { WorkspacePreviewResponse } from '../../lib/api/types';

const MOCK_WORKSPACE_PREVIEW: WorkspacePreviewResponse = {
  status: 'success',
  stack_id: 'test_amr_stack',
  stack_name: 'Test AMR Stack',
  workspace_name: 'test_amr_stack_ws',
  target_distro: 'humble',
  target_os: 'ubuntu-22.04',
  target_arch: 'x86_64',
  compatibility_verdict: 'COMPATIBLE',
  file_count: 12,
  total_bytes: 14500,
  file_tree: {
    name: 'root',
    type: 'directory',
    children: {
      'README.md': { name: 'README.md', type: 'file', size: 2800 },
      'openrobo.manifest.json': { name: 'openrobo.manifest.json', type: 'file', size: 1200 },
      'openrobo.lock.json': { name: 'openrobo.lock.json', type: 'file', size: 800 },
    },
  },
  files: {
    'README.md': '# Test AMR Stack â€” Generated ROS 2 Workspace\n\nDeterministic colcon setup.',
    'openrobo.manifest.json': '{\n  "id": "test_amr_stack"\n}',
    'openrobo.lock.json': '{\n  "lockfile_version": "1.0.0"\n}',
    'setup/install_dependencies.sh': '#!/usr/bin/env bash\nsudo apt-get update',
    'docker/Dockerfile': 'FROM ros:humble-ros-base AS base\nWORKDIR /openrobo_ws',
  },
  warnings: [],
  unsupported_components: [],
  selected_adapters: ['nav2', 'slam_toolbox'],
  generator_version: '0.5.0',
  generated_at: '2026-09-17T12:00:00Z',
};

describe('WorkspaceModal (Milestone 5 Web Integration)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders preview modal with file hierarchy, file contents, and download button', async () => {
    const previewSpy = vi
      .spyOn(apiClient, 'previewWorkspace')
      .mockResolvedValueOnce(MOCK_WORKSPACE_PREVIEW);

    render(
      <WorkspaceModal
        isOpen={true}
        onClose={vi.fn()}
        manifest={{ id: 'test_amr_stack' }}
        stackName="Test AMR Stack"
      />
    );

    expect(
      screen.getByText(/Synthesizing deterministic colcon workspace/i)
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(previewSpy).toHaveBeenCalled();
      expect(screen.getByText('Workspace & Deployment Generator')).toBeInTheDocument();
      expect(screen.getByText('COMPATIBLE')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();
      expect(screen.getByText(/Deterministic colcon setup/i)).toBeInTheDocument();
    });
  });

  it('switches selected file when clicking a file in the hierarchy', async () => {
    vi.spyOn(apiClient, 'previewWorkspace').mockResolvedValueOnce(MOCK_WORKSPACE_PREVIEW);

    render(
      <WorkspaceModal
        isOpen={true}
        onClose={vi.fn()}
        manifest={{ id: 'test_amr_stack' }}
        stackName="Test AMR Stack"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('openrobo.lock.json')).toBeInTheDocument();
    });

    const lockfileButton = screen.getByText('openrobo.lock.json');
    fireEvent.click(lockfileButton);

    await waitFor(() => {
      expect(screen.getByText(/lockfile_version/i)).toBeInTheDocument();
    });
  });

  it('triggers zip download on download button click', async () => {
    vi.spyOn(apiClient, 'previewWorkspace').mockResolvedValueOnce(MOCK_WORKSPACE_PREVIEW);
    const downloadSpy = vi
      .spyOn(apiClient, 'downloadWorkspaceZip')
      .mockResolvedValueOnce(new Blob(['fake zip bytes'], { type: 'application/zip' }));

    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:http://localhost/mock-blob');
    window.URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(
      <WorkspaceModal
        isOpen={true}
        onClose={vi.fn()}
        manifest={{ id: 'test_amr_stack' }}
        stackName="Test AMR Stack"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Download colcon Workspace/i)).toBeInTheDocument();
    });

    const downloadButton = screen.getByText(/Download colcon Workspace/i);
    fireEvent.click(downloadButton);

    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalled();
    });
  });
});