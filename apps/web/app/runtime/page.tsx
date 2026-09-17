'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  fetchProviders,
  fetchRosEnvironment,
  fetchConnectionInspector,
  fetchSimulators,
  fetchLiveGraph,
  fetchRuntimeSessions,
} from '../../lib/api/client';
import {
  ProviderInfo,
  RosEnvironmentInfo,
  ConnectionInspectorReport,
  SimulatorInfo,
  NodeHealth,
  ConnectionDiagnostic,
  RuntimeSession,
} from '../../lib/api/types';

// Mock/Demonstration fixtures for explicit Demo Mode ONLY
const DEMO_NODES: NodeHealth[] = [
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
];

const DEMO_CONNECTIONS: ConnectionDiagnostic[] = [
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
];

export default function RuntimeStudioPage() {
  const [demoMode, setDemoMode] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [providers, setProviders] = useState<Record<string, ProviderInfo>>({});
  const [rosEnv, setRosEnv] = useState<RosEnvironmentInfo | null>(null);
  const [connectionInspector, setConnectionInspector] = useState<ConnectionInspectorReport | null>(null);
  const [simulators, setSimulators] = useState<Record<string, SimulatorInfo>>({});
  const [sessions, setSessions] = useState<RuntimeSession[]>([]);

  const [liveNodes, setLiveNodes] = useState<NodeHealth[]>([]);
  const [liveConnections, setLiveConnections] = useState<ConnectionDiagnostic[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<ConnectionDiagnostic | null>(null);
  const [activeTab, setActiveTab] = useState<'graph' | 'nodes' | 'sessions' | 'inspector'>('graph');

  useEffect(() => {
    let mounted = true;

    async function loadRealRuntimeState() {
      setLoading(true);
      setError(null);
      try {
        const [provRes, envRes, ciRes, simRes, graphRes, sessRes] = await Promise.allSettled([
          fetchProviders(),
          fetchRosEnvironment(),
          fetchConnectionInspector(),
          fetchSimulators(),
          fetchLiveGraph(),
          fetchRuntimeSessions(),
        ]);

        if (!mounted) return;

        const anyCoreFailed = provRes.status === 'rejected' || envRes.status === 'rejected';
        if (anyCoreFailed) {
          setError('Unable to connect to OpenRobo Runtime API.');
        }

        if (provRes.status === 'fulfilled') setProviders(provRes.value);
        if (envRes.status === 'fulfilled') setRosEnv(envRes.value);
        if (ciRes.status === 'fulfilled') setConnectionInspector(ciRes.value);
        if (simRes.status === 'fulfilled') setSimulators(simRes.value);
        if (sessRes.status === 'fulfilled') setSessions(sessRes.value);

        if (graphRes.status === 'fulfilled') {
          const rawGraph = graphRes.value;
          const nodes: NodeHealth[] = (rawGraph.nodes || []).map((n: any) => ({
            name: n.name || 'unknown',
            namespace: n.namespace || '/',
            full_name: n.full_name,
            is_present: n.is_present ?? true,
            is_alive: n.is_alive ?? true,
            pid: n.pid,
            publisher_topics: n.publisher_topics || [],
            subscriber_topics: n.subscriber_topics || [],
            services: n.services || [],
            actions: n.actions || [],
          }));

          const conns: ConnectionDiagnostic[] = (rawGraph.topics || []).map((t: any) => ({
            topic: t.name || t.topic || 'unknown',
            topic_type: t.type || 'unknown',
            status: t.publishers?.length && t.subscribers?.length ? 'HEALTHY' : 'ORPHANED_PUBLISHER',
            publishers: t.publishers || [],
            subscribers: t.subscribers || [],
            rate_hz: t.rate_hz,
            qos_status: 'COMPATIBLE',
          }));

          setLiveNodes(nodes);
          setLiveConnections(conns);
          if (conns.length > 0) setSelectedTopic(conns[0]);
        }
      } catch (err: any) {
        if (mounted) setError(err?.message || 'Failed to connect to OpenRobo Runtime API.');
      } finally {
        if (mounted) setLoading(false);
      }
    }

    if (!demoMode) {
      loadRealRuntimeState();
    } else {
      setLiveNodes(DEMO_NODES);
      setLiveConnections(DEMO_CONNECTIONS);
      setSelectedTopic(DEMO_CONNECTIONS[0]);
      setLoading(false);
    }

    return () => {
      mounted = false;
    };
  }, [demoMode]);

  const activeNodes = demoMode ? DEMO_NODES : liveNodes;
  const activeConnections = demoMode ? DEMO_CONNECTIONS : liveConnections;

  // Truthful Readiness Calculation
  const readinessBadge = demoMode
    ? 'DEMO_DATA'
    : rosEnv?.status === 'AVAILABLE' && activeNodes.length > 0
    ? 'RUNTIME_VERIFIED'
    : 'RUNTIME_NOT_EXECUTED';

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
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <Link href="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>OpenRobo</span>
            <span
              style={{
                fontSize: '0.8rem',
                padding: '0.2rem 0.5rem',
                background: 'rgba(6,182,212,0.1)',
                color: 'var(--accent-cyan)',
                borderRadius: '4px',
                border: '1px solid rgba(6,182,212,0.3)',
              }}
            >
              Runtime Studio M6.1
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          {/* Demo Mode Toggle */}
          <button
            onClick={() => setDemoMode(!demoMode)}
            style={{
              fontSize: '0.8rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 600,
              background: demoMode ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              color: demoMode ? 'var(--accent-amber)' : 'var(--text-muted)',
              border: demoMode ? '1px solid var(--accent-amber)' : '1px solid var(--border-color)',
            }}
            data-testid="toggle-demo-mode"
          >
            {demoMode ? '● Demo Mode (Active)' : '○ Enable Demo Mode'}
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            <span>Readiness:</span>
            <span
              style={{
                color:
                  readinessBadge === 'RUNTIME_VERIFIED'
                    ? 'var(--accent-emerald)'
                    : readinessBadge === 'DEMO_DATA'
                    ? 'var(--accent-amber)'
                    : 'var(--text-dim)',
                fontWeight: 700,
                background:
                  readinessBadge === 'RUNTIME_VERIFIED'
                    ? 'rgba(16,185,129,0.1)'
                    : readinessBadge === 'DEMO_DATA'
                    ? 'rgba(245,158,11,0.1)'
                    : 'rgba(255,255,255,0.05)',
                padding: '0.2rem 0.6rem',
                borderRadius: '4px',
                border: '1px solid var(--border-color)',
              }}
              data-testid="runtime-status-badge"
            >
              {readinessBadge}
            </span>
          </div>
        </div>
      </header>

      {/* Demo Banner */}
      {demoMode && (
        <div
          style={{
            background: 'rgba(245, 158, 11, 0.1)',
            borderBottom: '1px solid rgba(245, 158, 11, 0.3)',
            color: 'var(--accent-amber)',
            padding: '0.6rem 2rem',
            fontSize: '0.85rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
          data-testid="demo-data-banner"
        >
          <span>DEMO DATA: Showing offline demonstration fixtures for SLAM Toolbox, RPLiDAR, and Nav2.</span>
          <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>Toggle off to connect to live ROS 2 backend.</span>
        </div>
      )}

      {/* Main Content */}
      <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem' }}>
        {error && (
          <div
            data-testid="runtime-error-banner"
            style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid var(--accent-red)',
              borderRadius: '6px',
              padding: '0.75rem 1rem',
              marginBottom: '1.5rem',
              fontSize: '0.85rem',
              color: 'var(--accent-red)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
            }}
          >
            <span style={{ fontWeight: 700 }}>Live Runtime API Unreachable:</span>
            <span>{error}</span>
          </div>
        )}

        {/* Top Info Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem', marginBottom: '2rem' }}>
          {/* Provider Status */}
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }} data-testid="providers-card">
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '0.75rem', textTransform: 'uppercase' }}>
              Execution Providers
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {Object.keys(providers).length > 0 ? (
                Object.entries(providers).map(([key, p]) => (
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
                ))
              ) : (
                <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
                  {loading ? 'Probing providers...' : 'No execution providers discovered.'}
                </span>
              )}
            </div>
          </div>

          {/* ROS Environment Status */}
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }} data-testid="ros-env-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
                ROS 2 Environment
              </h3>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: rosEnv?.status === 'AVAILABLE' ? 'var(--accent-emerald)' : 'var(--text-dim)',
                  background: rosEnv?.status === 'AVAILABLE' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.05)',
                  padding: '0.15rem 0.4rem',
                  borderRadius: '4px',
                }}
              >
                {rosEnv ? rosEnv.status : loading ? 'PROBING...' : 'UNAVAILABLE'}
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
              {rosEnv?.details || 'Probing local ROS 2 installation, rclpy, and RMW status.'}
            </p>
          </div>

          {/* Connection Inspector Status */}
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }} data-testid="connection-inspector-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase' }}>
                Connection Inspector
              </h3>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: connectionInspector?.status === 'AVAILABLE' ? 'var(--accent-emerald)' : 'var(--text-dim)',
                  background: connectionInspector?.status === 'AVAILABLE' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.05)',
                  padding: '0.15rem 0.4rem',
                  borderRadius: '4px',
                }}
              >
                {connectionInspector ? connectionInspector.status : 'NOT_INSTALLED'}
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.4', marginBottom: '0.5rem' }}>
              External tool integration for live ROS 2 connection diagnostics.
            </p>
            <div style={{ fontSize: '0.75rem', color: 'var(--accent-amber)', background: 'rgba(245, 158, 11, 0.08)', padding: '0.4rem', borderRadius: '4px', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
              <strong>License:</strong> GPL-3.0-only boundary. Process invocation only.
            </div>
          </div>

          {/* Simulator Status */}
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }} data-testid="simulators-card">
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-emerald)', marginBottom: '0.75rem', textTransform: 'uppercase' }}>
              Simulation Adapters
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {Object.keys(simulators).length > 0 ? (
                Object.entries(simulators).map(([key, s]) => (
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
                ))
              ) : (
                <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
                  {loading ? 'Probing simulators...' : 'No simulation adapters found.'}
                </span>
              )}
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
            ROS Graph & Connections ({activeConnections.length})
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
            Node Liveness ({activeNodes.length})
          </button>
          <button
            onClick={() => setActiveTab('sessions')}
            style={{
              padding: '0.6rem 1.2rem',
              background: activeTab === 'sessions' ? 'rgba(6,182,212,0.1)' : 'transparent',
              color: activeTab === 'sessions' ? 'var(--accent-cyan)' : 'var(--text-muted)',
              border: 'none',
              borderBottom: activeTab === 'sessions' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.9rem',
            }}
            data-testid="tab-sessions"
          >
            Sessions ({sessions.length})
          </button>
        </div>

        {/* Tab Content: Graph */}
        {activeTab === 'graph' && (
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
            {/* Connections Table */}
            <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
              <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-main)' }}>
                Active Topic Connections & QoS Evaluation
              </h4>
              {activeConnections.length > 0 ? (
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
                    {activeConnections.map((c) => (
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
              ) : (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  {loading ? 'Collecting live ROS graph...' : 'No active ROS topics observed. Start a ROS node or enable Demo Mode.'}
                </div>
              )}
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

        {/* Tab Content: Nodes */}
        {activeTab === 'nodes' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
            {activeNodes.length > 0 ? (
              activeNodes.map((n) => (
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
              ))
            ) : (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem', gridColumn: '1 / -1' }}>
                {loading ? 'Discovering active nodes...' : 'No active ROS nodes discovered.'}
              </div>
            )}
          </div>
        )}

        {/* Tab Content: Sessions */}
        {activeTab === 'sessions' && (
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
            <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-main)' }}>
              Tracked Runtime Sessions
            </h4>
            {sessions.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {sessions.map((s) => (
                  <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: '6px' }}>
                    <div>
                      <span style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{s.id}</span>
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Stack: {s.stack_id} | Distro: {s.ros_distro}</p>
                    </div>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', background: s.status === 'RUNNING' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.05)', color: s.status === 'RUNNING' ? 'var(--accent-emerald)' : 'var(--text-dim)' }}>
                      {s.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No active runtime sessions tracked.</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
