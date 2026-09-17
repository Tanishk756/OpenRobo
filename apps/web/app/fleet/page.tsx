'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import Navbar from '../../components/Navbar';

interface FleetDevice {
  id: string;
  name: string;
  domain: string;
  robot_type: string;
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE' | 'REVOKED' | 'ENROLLED';
  certificate_fingerprint: string;
  capabilities: string[];
  last_heartbeat_at?: string;
  created_at: string;
  updated_at: string;
}

interface DeviceDetail extends FleetDevice {
  certificate_serial?: string;
  revoked_at?: string;
  revocation_reason?: string;
  last_heartbeat?: Record<string, any>;
}

const DEMO_DEVICES: FleetDevice[] = [
  {
    id: '00000000-demo-0001-0000-000000000001',
    name: '[DEMO DATA] Robot Alpha (AMR Rover)',
    domain: 'ugv',
    robot_type: 'rover',
    status: 'ONLINE',
    certificate_fingerprint: 'ed25519:a1b2c3d4e5f60718293a4b5c6d7e8f9012345678',
    capabilities: ['ROS2_HUMBLE', 'NAV2', 'LIDAR_2D'],
    last_heartbeat_at: new Date().toISOString(),
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: '00000000-demo-0002-0000-000000000002',
    name: '[DEMO DATA] Robot Beta (Manipulator Arm)',
    domain: 'manipulation',
    robot_type: 'arm',
    status: 'DEGRADED',
    certificate_fingerprint: 'ed25519:f6e5d4c3b2a10987654321fedcba0987654321ab',
    capabilities: ['ROS2_HUMBLE', 'MOVEIT2', 'DEPTH_CAMERA'],
    last_heartbeat_at: new Date(Date.now() - 45000).toISOString(),
    created_at: new Date(Date.now() - 172800000).toISOString(),
    updated_at: new Date(Date.now() - 45000).toISOString(),
  },
  {
    id: '00000000-demo-0003-0000-000000000003',
    name: '[DEMO DATA] Robot Gamma (Drone Inspection)',
    domain: 'uav',
    robot_type: 'quadrotor',
    status: 'OFFLINE',
    certificate_fingerprint: 'ed25519:1234567890abcdef1234567890abcdef12345678',
    capabilities: ['PX4_AUTOPILOT', 'OPTICAL_FLOW'],
    last_heartbeat_at: new Date(Date.now() - 3600000).toISOString(),
    created_at: new Date(Date.now() - 604800000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
  },
];

export default function FleetStudioPage() {
  const [devices, setDevices] = useState<FleetDevice[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<DeviceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDemoMode, setIsDemoMode] = useState(false);

  const [tokenDeviceName, setTokenDeviceName] = useState('');
  const [tokenDomain, setTokenDomain] = useState('ugv');
  const [tokenRobotType, setTokenRobotType] = useState('rover');
  const [issuedTokenData, setIssuedTokenData] = useState<{ token: string; token_id: string; expires_at: string; device_name: string } | null>(null);
  const [issuingToken, setIssuingToken] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);

  const [revocationReason, setRevocationReason] = useState('Decommissioned by admin');
  const [revoking, setRevoking] = useState(false);

  const activeFetchId = useRef(0);

  const refreshFleet = useCallback(async (demoMode: boolean) => {
    const fetchId = ++activeFetchId.current;
    if (demoMode) {
      setDevices(DEMO_DEVICES);
      setLoading(false);
      setError(null);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await fetch('http://localhost:8000/api/v1/fleet/devices');
      if (fetchId !== activeFetchId.current) return;
      if (!res.ok) {
        throw new Error(`Failed to load devices: ${res.statusText}`);
      }
      const data = await res.json();
      if (fetchId !== activeFetchId.current) return;
      setDevices(data);
    } catch (err: any) {
      if (fetchId !== activeFetchId.current) return;
      console.warn('Could not fetch live devices:', err);
      setError(err.message || 'Error connecting to API. You may enable Demo Data mode to explore the UI.');
      setDevices([]);
    } finally {
      if (fetchId === activeFetchId.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    refreshFleet(isDemoMode);
  }, [isDemoMode, refreshFleet]);

  const handleIssueToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenDeviceName.trim()) return;
    try {
      setIssuingToken(true);
      setTokenError(null);
      const res = await fetch('http://localhost:8000/api/v1/fleet/enrollment-tokens', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_name: tokenDeviceName.trim(),
          domain: tokenDomain,
          robot_type: tokenRobotType,
          expires_in_hours: 24,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to issue enrollment token');
      }
      const data = await res.json();
      setIssuedTokenData(data);
      setTokenDeviceName('');
    } catch (err: any) {
      setTokenError(err.message || 'Token generation failed');
    } finally {
      setIssuingToken(false);
    }
  };

  const handleInspectDevice = async (deviceId: string) => {
    if (isDemoMode) {
      const demo = DEMO_DEVICES.find((d) => d.id === deviceId);
      if (demo) {
        setSelectedDevice({
          ...demo,
          certificate_serial: '0x1234567890ABCDEF',
          last_heartbeat: {
            battery_percentage: 84.5,
            cpu_percent: 14.2,
            memory_used_mb: 1820,
            memory_total_mb: 8192,
            active_nodes_count: 8,
            active_topics_count: 24,
            ros_distro: 'humble',
            status: demo.status,
          },
        });
      }
      return;
    }
    try {
      const res = await fetch(`http://localhost:8000/api/v1/fleet/devices/${deviceId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedDevice(data);
      }
    } catch (err) {
      console.error('Failed to load device details:', err);
    }
  };

  const handleRevokeDevice = async (deviceId: string) => {
    if (!confirm('Are you sure you want to REVOKE this device? Its certificate will be immediately invalidated and all future connections rejected.')) {
      return;
    }
    try {
      setRevoking(true);
      if (!isDemoMode) {
        const res = await fetch(`http://localhost:8000/api/v1/fleet/devices/${deviceId}/revoke`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: revocationReason }),
        });
        if (!res.ok) {
          throw new Error('Revocation failed');
        }
      }
      if (selectedDevice && selectedDevice.id === deviceId) {
        setSelectedDevice({
          ...selectedDevice,
          status: 'REVOKED',
          revoked_at: new Date().toISOString(),
          revocation_reason: revocationReason,
        });
      }
      refreshFleet(isDemoMode);
    } catch (err: any) {
      alert(err.message || 'Could not revoke device');
    } finally {
      setRevoking(false);
    }
  };

  const onlineCount = devices.filter((d) => d.status === 'ONLINE').length;
  const degradedCount = devices.filter((d) => d.status === 'DEGRADED').length;
  const offlineCount = devices.filter((d) => d.status === 'OFFLINE').length;
  const revokedCount = devices.filter((d) => d.status === 'REVOKED').length;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-800 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-white">Fleet Studio</h1>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                MILESTONE 7.1 FOUNDATION
              </span>
              {isDemoMode && (
                <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  DEMO DATA ACTIVE
                </span>
              )}
            </div>
            <p className="text-sm text-neutral-400 mt-1">
              Cryptographic X.509 device identity, mTLS enrollment, real-time heartbeat status, and telemetry streams.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              data-testid="toggle-demo-btn"
              onClick={() => setIsDemoMode(!isDemoMode)}
              className={`px-3 py-1.5 text-xs font-medium rounded border transition ${
                isDemoMode
                  ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
                  : 'bg-neutral-900 border-neutral-800 text-neutral-400 hover:text-neutral-200'
              }`}
            >
              {isDemoMode ? 'Exit Demo Mode' : 'Explore with Demo Data'}
            </button>
            <button
              onClick={() => refreshFleet(isDemoMode)}
              className="px-3 py-1.5 text-xs font-medium rounded bg-cyan-600 hover:bg-cyan-500 text-white transition"
            >
              Refresh Fleet
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <div className="p-4 rounded-lg bg-neutral-900/60 border border-neutral-800">
            <div className="text-xs text-neutral-400 uppercase tracking-wider font-semibold">Total Registered</div>
            <div data-testid="metric-total-devices" className="text-2xl font-bold text-white mt-1">
              {devices.length}
            </div>
          </div>
          <div className="p-4 rounded-lg bg-neutral-900/60 border border-neutral-800">
            <div className="text-xs text-emerald-400 uppercase tracking-wider font-semibold">Online</div>
            <div data-testid="metric-online-devices" className="text-2xl font-bold text-emerald-400 mt-1">
              {onlineCount}
            </div>
          </div>
          <div className="p-4 rounded-lg bg-neutral-900/60 border border-neutral-800">
            <div className="text-xs text-amber-400 uppercase tracking-wider font-semibold">Degraded</div>
            <div data-testid="metric-degraded-devices" className="text-2xl font-bold text-amber-400 mt-1">
              {degradedCount}
            </div>
          </div>
          <div className="p-4 rounded-lg bg-neutral-900/60 border border-neutral-800">
            <div className="text-xs text-neutral-400 uppercase tracking-wider font-semibold">Offline</div>
            <div data-testid="metric-offline-devices" className="text-2xl font-bold text-neutral-400 mt-1">
              {offlineCount}
            </div>
          </div>
          <div className="p-4 rounded-lg bg-neutral-900/60 border border-neutral-800">
            <div className="text-xs text-rose-400 uppercase tracking-wider font-semibold">Revoked</div>
            <div data-testid="metric-revoked-devices" className="text-2xl font-bold text-rose-400 mt-1">
              {revokedCount}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 overflow-hidden">
              <div className="px-4 py-3 border-b border-neutral-800 bg-neutral-900/80 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">Enrolled Fleet Nodes</h2>
                <span className="text-xs text-neutral-400">Derived state via sliding heartbeat window</span>
              </div>

              {loading ? (
                <div className="p-8 text-center text-neutral-400 text-sm">Loading fleet devices...</div>
              ) : error && !isDemoMode && devices.length === 0 ? (
                <div className="p-8 text-center text-sm space-y-3">
                  <div className="text-amber-400 font-medium">Control Plane Offline or No Devices</div>
                  <p className="text-neutral-400 max-w-md mx-auto text-xs">{error}</p>
                  <button
                    data-testid="btn-enable-demo-fallback"
                    onClick={() => setIsDemoMode(true)}
                    className="px-3 py-1.5 text-xs bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded hover:bg-amber-500/30 transition"
                  >
                    View Demo Fleet
                  </button>
                </div>
              ) : devices.length === 0 ? (
                <div className="p-8 text-center text-neutral-400 text-sm space-y-2">
                  <p>No devices enrolled yet.</p>
                  <p className="text-xs text-neutral-500">Issue a single-use token on the right to enroll a robot agent.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-neutral-300">
                    <thead className="bg-neutral-950/50 text-neutral-400 uppercase tracking-wider font-semibold border-b border-neutral-800">
                      <tr>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Device Name</th>
                        <th className="py-3 px-4">Domain / Type</th>
                        <th className="py-3 px-4">Fingerprint</th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800/60">
                      {devices.map((device) => {
                        const statusColors: Record<string, string> = {
                          ONLINE: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
                          DEGRADED: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
                          OFFLINE: 'bg-neutral-800 text-neutral-400 border-neutral-700',
                          REVOKED: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
                          ENROLLED: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
                        };

                        return (
                          <tr key={device.id} className="hover:bg-neutral-800/30 transition">
                            <td className="py-3 px-4 whitespace-nowrap">
                              <span className={`px-2 py-0.5 font-semibold text-[10px] rounded border ${statusColors[device.status] || ''}`}>
                                {device.status}
                              </span>
                            </td>
                            <td className="py-3 px-4 font-medium text-white">
                              <div>{device.name}</div>
                              <div className="text-[10px] text-neutral-500 font-mono">{device.id}</div>
                            </td>
                            <td className="py-3 px-4">
                              <span className="text-neutral-300 font-medium capitalize">{device.domain}</span>
                              <span className="text-neutral-500 text-[10px] block capitalize">{device.robot_type}</span>
                            </td>
                            <td className="py-3 px-4 font-mono text-[11px] text-neutral-400 truncate max-w-[120px]" title={device.certificate_fingerprint}>
                              {device.certificate_fingerprint ? device.certificate_fingerprint.slice(0, 16) + '...' : 'N/A'}
                            </td>
                            <td className="py-3 px-4 text-right whitespace-nowrap">
                              <button
                                data-testid={`inspect-btn-${device.id}`}
                                onClick={() => handleInspectDevice(device.id)}
                                className="px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded font-medium transition text-xs"
                              >
                                Inspect
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
              <h2 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider mb-2">Issue Enrollment Token</h2>
              <p className="text-xs text-neutral-400 mb-4">
                Generate a cryptographically secure, single-use enrollment token for bootstrapping agent X.509 certificates.
              </p>

              <form onSubmit={handleIssueToken} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1">Device Name</label>
                  <input
                    type="text"
                    data-testid="input-token-device-name"
                    placeholder="e.g. turtlebot-ugv-01"
                    value={tokenDeviceName}
                    onChange={(e) => setTokenDeviceName(e.target.value)}
                    required
                    className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-neutral-300 mb-1">Domain</label>
                    <select
                      value={tokenDomain}
                      onChange={(e) => setTokenDomain(e.target.value)}
                      className="w-full px-2 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs text-white focus:outline-none focus:border-cyan-500"
                    >
                      <option value="ugv">UGV (Ground)</option>
                      <option value="manipulation">Manipulator Arm</option>
                      <option value="uav">UAV (Aerial)</option>
                      <option value="humanoid">Humanoid</option>
                      <option value="general">General Robotics</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-300 mb-1">Robot Type</label>
                    <input
                      type="text"
                      value={tokenRobotType}
                      onChange={(e) => setTokenRobotType(e.target.value)}
                      placeholder="e.g. rover"
                      className="w-full px-2 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs text-white focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>

                {tokenError && <div className="p-2 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded">{tokenError}</div>}

                <button
                  type="submit"
                  data-testid="btn-issue-token"
                  disabled={issuingToken || !tokenDeviceName.trim()}
                  className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded font-medium text-xs transition"
                >
                  {issuingToken ? 'Generating Token...' : 'Generate Single-Use Token'}
                </button>
              </form>

              {issuedTokenData && (
                <div data-testid="issued-token-panel" className="mt-4 p-3 bg-neutral-950 border border-cyan-500/30 rounded space-y-2">
                  <div className="text-[11px] font-semibold text-cyan-400 uppercase tracking-wider">Enrollment Token Issued</div>
                  <div className="text-xs text-neutral-400">Provide this token to the agent CLI during bootstrap:</div>
                  <div className="p-2 bg-neutral-900 rounded font-mono text-[11px] text-amber-300 break-all border border-neutral-800 select-all">
                    {issuedTokenData.token}
                  </div>
                  <div className="text-[10px] text-neutral-500 space-y-0.5">
                    <div>Expires: {new Date(issuedTokenData.expires_at).toLocaleString()}</div>
                    <div>Agent Command: <code className="text-neutral-300 font-mono">openrobo agent enroll --token {issuedTokenData.token.slice(0, 16)}...</code></div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {selectedDevice && (
          <div data-testid="device-details-drawer" className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  {selectedDevice.name}
                  <span className="text-xs font-normal text-neutral-400 font-mono">({selectedDevice.id})</span>
                </h3>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Domain: <span className="text-neutral-200 capitalize">{selectedDevice.domain}</span> | Type: <span className="text-neutral-200 capitalize">{selectedDevice.robot_type}</span>
                </p>
              </div>
              <button
                onClick={() => setSelectedDevice(null)}
                className="text-neutral-400 hover:text-white text-xs px-2 py-1 rounded bg-neutral-800"
              >
                Close Drawer
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="space-y-2 p-3 bg-neutral-950/60 rounded border border-neutral-800/80">
                <div className="font-semibold text-neutral-300 uppercase tracking-wider text-[11px]">Cryptographic Identity</div>
                <div className="space-y-1 text-neutral-400 font-mono text-[11px]">
                  <div>Status: <span className="text-white font-sans font-semibold">{selectedDevice.status}</span></div>
                  <div>Fingerprint (SHA-256): <span className="text-cyan-300 break-all">{selectedDevice.certificate_fingerprint || 'None'}</span></div>
                  <div>Cert Serial: <span className="text-neutral-300">{selectedDevice.certificate_serial || 'N/A'}</span></div>
                  <div>Enrolled At: <span className="text-neutral-300 font-sans">{new Date(selectedDevice.created_at).toLocaleString()}</span></div>
                  {selectedDevice.revoked_at && (
                    <div className="text-rose-400">Revoked At: {new Date(selectedDevice.revoked_at).toLocaleString()} ({selectedDevice.revocation_reason})</div>
                  )}
                </div>
              </div>

              <div className="space-y-2 p-3 bg-neutral-950/60 rounded border border-neutral-800/80">
                <div className="font-semibold text-neutral-300 uppercase tracking-wider text-[11px]">Telemetry & Diagnostics</div>
                {selectedDevice.last_heartbeat ? (
                  <div className="space-y-1 text-neutral-300">
                    <div>ROS Distro: <span className="text-white font-medium">{selectedDevice.last_heartbeat.ros_distro || 'Unknown'}</span></div>
                    <div>Battery: <span className="text-emerald-400 font-medium">{selectedDevice.last_heartbeat.battery_percentage ?? 'N/A'}%</span></div>
                    <div>CPU / Memory: <span className="text-white">{selectedDevice.last_heartbeat.cpu_percent}% CPU / {selectedDevice.last_heartbeat.memory_used_mb} MB RAM</span></div>
                    <div>Active Graph: <span className="text-white">{selectedDevice.last_heartbeat.active_nodes_count} Nodes, {selectedDevice.last_heartbeat.active_topics_count} Topics</span></div>
                  </div>
                ) : (
                  <div className="text-neutral-500 italic">No live heartbeat telemetry recorded yet.</div>
                )}
              </div>
            </div>

            {selectedDevice.status !== 'REVOKED' && (
              <div className="flex items-center justify-end gap-3 pt-2 border-t border-neutral-800/80">
                <input
                  type="text"
                  placeholder="Revocation reason..."
                  value={revocationReason}
                  onChange={(e) => setRevocationReason(e.target.value)}
                  className="px-3 py-1 bg-neutral-950 border border-neutral-800 rounded text-xs text-white max-w-xs focus:outline-none"
                />
                <button
                  data-testid="btn-revoke-device"
                  disabled={revoking}
                  onClick={() => handleRevokeDevice(selectedDevice.id)}
                  className="px-3 py-1 bg-rose-600/20 hover:bg-rose-600/40 text-rose-300 border border-rose-600/40 rounded text-xs font-semibold transition disabled:opacity-50"
                >
                  {revoking ? 'Revoking...' : 'Revoke Device Access'}
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
