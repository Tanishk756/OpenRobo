import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FleetStudioPage from '../../app/fleet/page';

describe('FleetStudioPage (Milestone 7.1)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
  });

  it('renders Fleet Studio header, queries devices, and displays metrics', async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: '11111111-1111-1111-1111-111111111111',
          name: 'robot-alpha',
          domain: 'ugv',
          robot_type: 'rover',
          status: 'ONLINE',
          certificate_fingerprint: 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
          capabilities: ['ROS2_HUMBLE', 'GAZEBO'],
          last_heartbeat_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
    });

    render(<FleetStudioPage />);

    expect(screen.getByRole('heading', { level: 1, name: /Fleet Studio/i })).toBeInTheDocument();
    expect(screen.getByText(/MILESTONE 7.1/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('metric-total-devices')).toHaveTextContent('1');
      expect(screen.getByTestId('metric-online-devices')).toHaveTextContent('1');
      expect(screen.getByText(/robot-alpha/i)).toBeInTheDocument();
    });
  });

  it('issues a single-use enrollment token', async () => {
    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          token: 'orb_tok_test_sample_12345',
          token_id: 'tok-uuid-001',
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          device_name: 'rover-01',
        }),
      });

    render(<FleetStudioPage />);

    const input = screen.getByTestId('input-token-device-name');
    fireEvent.change(input, { target: { value: 'rover-01' } });

    const btn = screen.getByTestId('btn-issue-token');
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByTestId('issued-token-panel')).toBeInTheDocument();
      expect(screen.getByText(/orb_tok_test_sample_12345/i)).toBeInTheDocument();
    });
  });

  it('enables Demo Data mode and inspects device details', async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => [],
    });

    render(<FleetStudioPage />);

    const demoBtn = screen.getByTestId('toggle-demo-btn');
    fireEvent.click(demoBtn);

    await waitFor(() => {
      expect(screen.getByText(/DEMO DATA ACTIVE/i)).toBeInTheDocument();
      expect(screen.getByText(/\[DEMO DATA\] Robot Alpha/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId('inspect-btn-00000000-demo-0001-0000-000000000001')).toBeInTheDocument();
    });

    const inspectBtn = screen.getByTestId('inspect-btn-00000000-demo-0001-0000-000000000001');
    fireEvent.click(inspectBtn);

    await waitFor(() => {
      expect(screen.getByTestId('device-details-drawer')).toBeInTheDocument();
      expect(screen.getByTestId('btn-revoke-device')).toBeInTheDocument();
    });
  });
});
