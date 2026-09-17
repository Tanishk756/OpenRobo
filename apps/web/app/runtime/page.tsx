'use client';

import React, { useState } from 'react';
import Link from 'next/link';

interface ProviderInfo {
  provider_type: string;
  status: 'AVAILABLE' | 'UNAVAILABLE' | 'ERROR';
  version?: string;
  details?: string;
}

interface ConnectionInspectorInfo {
  status: string;
  detected_prefix?: string;
  version?: string;
  executables: string[];
  licensing_notice: string;
  integration_mode: string;
}

interface SimulatorInfo {
  simulator: string;
  installed: boolean;
  version?: string;
  details?: string;
}

interface NodeHealth {
  name: string;
  namespace: string;
  is_present: boolean;
  is_alive: boolean;
  pid?: number;
  publisher_topics: string[];
  subscriber_topics: string[];
  services: string[];
  actions: string[];
}

interface ConnectionDiagnostic {
  topic: string;
  topic_type: string;
  status: string;
  publishers: string[];
  subscribers: string[];
  rate_hz?: number;
  qos_status: string;
  qos_reason?: string;
}

export default function RuntimeStudioPage() {
  const [providers] = useState<Record<string, ProviderInfo>>({
    docker: { provider_type: 'docker', status: 'UNAVAILABLE', details: 'Docker daemon not running' },
    podman: { provider_type: 'podman', status: 'UNAVAILABLE', details: 'Podman CLI not found' },
    local_process: { provider_type: 'local_process', status: 'AVAILABLE', details: 'Local OS process execution' },
  });

  const [connectionInspector] = useState<ConnectionInspectorInfo>({
    status: 'NOT_INSTALLED',
    executables: [],
    licensing_notice: 'External GPL-3.0-only tool: OpenRobo communicates via external process boundary only.',
    integration_mode: 'external_process_cli',
  });

  const [simulators] = useState<Record<string, SimulatorInfo>>({
    gazebo: { simulator: 'gazebo', installed: false, details: 'Gazebo (gz/ign) CLI not found' },
    webots: { simulator: 'webots', installed: false, details: 'Webots executable not found' },
    mujoco: { simulator: 'mujoco', installed: false, details: 'MuJoCo runtime not detected' },
  });

  const [nodes] = useState<NodeHealth[]>([
    {
      name: 'slam_toolbox',
      namespace: '/',
      is_present: true,
      is_alive: true,
      publisher_topics: ['/map', '/tf'],
      subscriber_topics: ['/scan'],
      services: ['/slam_toolbox/save_map'],
      actions: [],
    },
    {
      name: 'rplidar_node',
      namespace: '/',
      is_present: true,
      is_alive: true,
      publisher_topics: ['/scan'],
      subscriber_topics: [],
      services: [],
      actions: [],
    },
    {
      name: 'nav2_controller',
      namespace: '/',
      is_present: true,
      is_alive: true,
      publisher_topics: ['/cmd_vel'],
      subscriber_topics: ['/map', '/odom'],
      services: [],
      actions: ['/navigate_to_pose'],
    },
  ]);

  const [connections] = useState<ConnectionDiagnostic[]>([
    {
      topic: '/scan',
      topic_type: 'sensor_msgs/msg/LaserScan',
      status: 'HEALTHY',
      publishers: ['rplidar_node'],
      subscribers: ['slam_toolbox'],
      rate_hz: 10.2,
      qos_status: 'COMPATIBLE',
    },
    {
      topic: '/map',
      topic_type: 'nav_msgs/msg/OccupancyGrid',
      status: 'HEALTHY',
      publishers: ['slam_toolbox'],
      subscribers: ['nav2_controller'],
      rate_hz: 1.0,
      qos_status: 'COMPATIBLE',
    },
    {
      topic: '/cmd_vel',
      topic_type: 'geometry_msgs/msg/Twist',
      status: 'ORPHANED_PUBLISHER',
      publishers: ['nav2_controller'],
      subscribers: [],
      rate_hz: 20.0,
      qos_status: 'COMPATIBLE',
    },
  ]);

  const [selectedTopic, setSelectedTopic] = useState<ConnectionDiagnostic | null>(connections[0]);
  const [activeTab, setActiveTab] = useState<'graph' | 'nodes' | 'simulators' | 'inspector'>('graph');

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-color)', color: 'var(--text-main)' }}>
      {/* Top Header */}
      <header
        style={{
          borderBottom: '1px solid var(--border-color)',
          background: 'var(--panel-bg)',
          padding: '1rem 2rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <Link href="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>OpenRobo</span>
            <span style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', background: 'rgba(6,182,212,0.1)', color: 'var(--accent-cyan)', borderRadius: '4px', border: '1px solid rgba(6,182,212,0.3)' }}>
              Runtime Studio M6
            </span>
          </Link>

          <nav style={{ display: 'flex', gap: '1rem', marginLeft: '1rem' }}>
            <Link href="/resources" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '0.9rem' }}>
              Resources
            </Link>
            <Link href="/stack-builder" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '0.9rem' }}>
              Stack Builder
            </Link>
            <Link href="/runtime" style={{ color: 'var(--accent-cyan)', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 600 }}>
              Runtime Studio
            </Link>
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            <span>Verification Status:</span>
            <span style={{ color: 'var(--accent-emerald)', fontWeight: 700, background: 'rgba(16,185,129,0.1)', padding: '0.2rem 0.6rem', borderRadius: '4px', border: '1px solid rgba(16,185,129,0.3)' }} data-testid="runtime-status-badge">
              BUILD_VERIFIED
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem' }}>
        {/* Top Info Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.25rem', marginBottom: '2rem' }}>
          {/* Provider Status */}
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }} data-testid="providers-card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '0.75rem', textTransform: 'uppercase' }}>
              Execution Providers
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {Object.entries(providers).map(([key, p]) => (
                <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                  <span style={{ textTransform: 'capitalize', color: 'var(--text-main)' }}>{key.replace('_', ' ')}:</span>
                  <span
                    style={{
                      color: p.status === 'AVAILABLE' ? 'var(--accent-emerald)' : 'var(--text-dim)',
                      fontWeight: 600,
                      background: p.status === 'AVAILABLE' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.05)',
                      padding: '0.15rem 0.4rem',
                      borderRadius: '4px',
                    }}
                  >
                    {p.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Connection Inspector Status */}
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }} data-testid="connection-inspector-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase' }}>
                Connection Inspector
              </h3>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: connectionInspector.status === 'INSTALLED' ? 'var(--accent-emerald)' : 'var(--text-dim)',
                  background: connectionInspector.status === 'INSTALLED' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.05)',
                  padding: '0.15rem 0.4rem',
                  borderRadius: '4px',
                }}
              >
                {connectionInspector.status}
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.4', marginBottom: '0.5rem' }}>
              External tool integration for live ROS 2 connection diagnostics.
            </p>
            <div style={{ fontSize: '0.75rem', color: 'var(--accent-amber)', background: 'rgba(245, 158, 11, 0.08)', padding: '0.5rem', borderRadius: '4px', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
              <strong>License Notice:</strong> GPL-3.0-only tool boundary. Safe CLI/process execution.
            </div>
          </div>

          {/* Simulator Status */}
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }} data-testid="simulators-card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-emerald)', marginBottom: '0.75rem', textTransform: 'uppercase' }}>
              Simulation Adapters
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {Object.entries(simulators).map(([key, s]) => (
                <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                  <span style={{ textTransform: 'capitalize', color: 'var(--text-main)' }}>{key}:</span>
                  <span
                    style={{
                      color: s.installed ? 'var(--accent-emerald)' : 'var(--text-dim)',
                      fontWeight: 600,
                      background: s.installed ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.05)',
                      padding: '0.15rem 0.4rem',
                      borderRadius: '4px',
                    }}
                  >
                    {s.installed ? 'Installed' : 'Not Detected'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', marginBottom: '1.5rem' }}>
          <button
            onClick={() => setActiveTab('graph')}
            style={{
              padding: '0.6rem 1.2rem',
              background: activeTab === 'graph' ? 'rgba(6,182,212,0.1)' : 'transparent',
              color: activeTab === 'graph' ? 'var(--accent-cyan)' : 'var(--text-muted)',
              border: 'none',
              borderBottom: activeTab === 'graph' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.9rem',
            }}
            data-testid="tab-graph"
          >
            ROS Graph & Connections ({connections.length})
          </button>
          <button
            onClick={() => setActiveTab('nodes')}
            style={{
              padding: '0.6rem 1.2rem',
              background: activeTab === 'nodes' ? 'rgba(6,182,212,0.1)' : 'transparent',
              color: activeTab === 'nodes' ? 'var(--accent-cyan)' : 'var(--text-muted)',
              border: 'none',
              borderBottom: activeTab === 'nodes' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.9rem',
            }}
            data-testid="tab-nodes"
          >
            Node Liveness ({nodes.length})
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'graph' && (
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
            {/* Connections Table */}
            <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
              <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-main)' }}>
                Active Topic Connections & QoS Evaluation
              </h4>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', textAlign: 'left' }}>
                    <th style={{ padding: '0.5rem' }}>Topic</th>
                    <th style={{ padding: '0.5rem' }}>Message Type</th>
                    <th style={{ padding: '0.5rem' }}>Status</th>
                    <th style={{ padding: '0.5rem' }}>Rate</th>
                    <th style={{ padding: '0.5rem' }}>QoS</th>
                  </tr>
                </thead>
                <tbody>
                  {connections.map((c) => (
                    <tr
                      key={c.topic}
                      onClick={() => setSelectedTopic(c)}
                      style={{
                        borderBottom: '1px solid var(--border-color)',
                        cursor: 'pointer',
                        background: selectedTopic?.topic === c.topic ? 'rgba(6,182,212,0.08)' : 'transparent',
                      }}
                      data-testid={`topic-row-${c.topic.replace('/', '')}`}
                    >
                      <td style={{ padding: '0.75rem 0.5rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>{c.topic}</td>
                      <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{c.topic_type}</td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <span
                          style={{
                            padding: '0.15rem 0.4rem',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            background: c.status === 'HEALTHY' ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)',
                            color: c.status === 'HEALTHY' ? 'var(--accent-emerald)' : 'var(--accent-amber)',
                          }}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>{c.rate_hz ? `${c.rate_hz} Hz` : 'N/A'}</td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <span style={{ color: c.qos_status === 'COMPATIBLE' ? 'var(--accent-emerald)' : 'var(--accent-red)' }}>
                          {c.qos_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Topic Inspector Panel */}
            <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
              <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-main)' }}>
                Topic Connection Inspector
              </h4>
              {selectedTopic ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Topic:</span>
                    <p style={{ fontWeight: 600, color: 'var(--accent-cyan)', marginTop: '0.2rem' }}>{selectedTopic.topic}</p>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Message Type:</span>
                    <p style={{ fontFamily: 'monospace', color: 'var(--text-main)', marginTop: '0.2rem' }}>{selectedTopic.topic_type}</p>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Publishers:</span>
                    <p style={{ color: 'var(--accent-emerald)', marginTop: '0.2rem' }}>
                      {selectedTopic.publishers.length > 0 ? selectedTopic.publishers.join(', ') : 'None (Orphaned)'}
                    </p>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Subscribers:</span>
                    <p style={{ color: 'var(--accent-blue)', marginTop: '0.2rem' }}>
                      {selectedTopic.subscribers.length > 0 ? selectedTopic.subscribers.join(', ') : 'None (Orphaned)'}
                    </p>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>QoS Compatibility:</span>
                    <p style={{ color: selectedTopic.qos_status === 'COMPATIBLE' ? 'var(--accent-emerald)' : 'var(--accent-red)', marginTop: '0.2rem' }}>
                      {selectedTopic.qos_status}
                    </p>
                  </div>
                </div>
              ) : (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Select a topic connection to view QoS diagnostics.</p>
              )}
            </div>
          </div>
        )}

        {/* Nodes Tab */}
        {activeTab === 'nodes' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
            {nodes.map((n) => (
              <div key={n.name} style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }} data-testid={`node-card-${n.name}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>{n.name}</h4>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-emerald)', background: 'rgba(16,185,129,0.1)', padding: '0.15rem 0.4rem', borderRadius: '4px' }}>
                    ALIVE
                  </span>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Namespace: {n.namespace}</p>
                <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                  <div>
                    <strong>Publishing:</strong> {n.publisher_topics.join(', ') || 'None'}
                  </div>
                  <div>
                    <strong>Subscribing:</strong> {n.subscriber_topics.join(', ') || 'None'}
                  </div>
                  <div>
                    <strong>Services:</strong> {n.services.join(', ') || 'None'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
