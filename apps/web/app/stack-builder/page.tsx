'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { WorkspaceModal } from './WorkspaceModal';
import {
  fetchResources,
  fetchStackTemplates,
  validateAdhocStack,
  resolveAdhocStack,
  createStack,
  importStackManifest,
} from '../../lib/api/client';
import {
  CompatibilityStatus,
  ProposedComponentAction,
  ResolutionProposal,
  Resource,
  StackComponent,
  StackTemplate,
  StackValidationResponse,
} from '../../lib/api/types';

const CATEGORIES = [
  { id: 'sensors', label: 'Sensors & Drivers', icon: '??' },
  { id: 'middleware', label: 'Middleware & DDS', icon: '?' },
  { id: 'perception', label: 'Perception & Vision', icon: '???' },
  { id: 'mapping', label: 'Localization & SLAM', icon: '???' },
  { id: 'navigation', label: 'Navigation & Planning', icon: '??' },
  { id: 'control', label: 'Control & Actuation', icon: '??' },
  { id: 'simulation', label: 'Simulation & Visualization', icon: '??' },
  { id: 'general', label: 'General Packages', icon: '??' },
];

export default function StackBuilderPage() {
  const [stackName, setStackName] = useState('autonomous_robot_stack');
  const [stackDescription, setStackDescription] = useState('Assembled robotics software pipeline');
  const [robotDomain, setRobotDomain] = useState('mobile_robotics');
  const [robotType, setRobotType] = useState('differential_drive');
  const [targetRosDistro, setTargetRosDistro] = useState('jazzy');
  const [targetOs, setTargetOs] = useState('ubuntu_24_04');
  const [targetArch, setTargetArch] = useState('x86_64');

  const [selectedComponents, setSelectedComponents] = useState<StackComponent[]>([]);
  const [librarySearch, setLibrarySearch] = useState('');
  const [libraryDomainFilter, setLibraryDomainFilter] = useState('');
  const [availableResources, setAvailableResources] = useState<Resource[]>([]);
  const [isLibraryLoading, setIsLibraryLoading] = useState(false);

  const [templates, setTemplates] = useState<StackTemplate[]>([]);
  const [validationResult, setValidationResult] = useState<StackValidationResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [activeTab, setActiveTab] = useState<'diagnostics' | 'graph' | 'manifest'>('diagnostics');

  const [resolutionProposal, setResolutionProposal] = useState<ResolutionProposal | null>(null);
  const [isResolving, setIsResolving] = useState(false);
  const [showResolveModal, setShowResolveModal] = useState(false);

  const [showImportModal, setShowImportModal] = useState(false);
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false);
  const [importText, setImportText] = useState('');
  const [importError, setImportError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'modified' | 'saving'>('saved');

  useEffect(() => {
    async function init() {
      setIsLibraryLoading(true);
      try {
        const [resList, tmplList] = await Promise.all([
          fetchResources({ limit: 50 }),
          fetchStackTemplates().catch(() => []),
        ]);
        setAvailableResources(resList.items);
        setTemplates(tmplList);
      } catch (err) {
        console.error('Failed to load initial library data', err);
      } finally {
        setIsLibraryLoading(false);
      }
    }
    init();
  }, []);

  const filteredLibrary = availableResources.filter((res) => {
    const matchesSearch =
      !librarySearch ||
      res.name.toLowerCase().includes(librarySearch.toLowerCase()) ||
      res.id.toLowerCase().includes(librarySearch.toLowerCase()) ||
      (res.summary && res.summary.toLowerCase().includes(librarySearch.toLowerCase()));
    const matchesDomain =
      !libraryDomainFilter ||
      (res.robotics_domains && res.robotics_domains.includes(libraryDomainFilter)) ||
      res.type.toLowerCase().includes(libraryDomainFilter.toLowerCase());
    return matchesSearch && matchesDomain;
  });

  const runValidation = useCallback(async () => {
    if (selectedComponents.length === 0) {
      setValidationResult(null);
      return;
    }
    setIsValidating(true);
    try {
      const res = await validateAdhocStack({
        components: selectedComponents,
        target_os: targetOs,
        target_arch: targetArch,
        target_ros_distro: targetRosDistro,
      });
      setValidationResult(res);
      if (res.resolution_proposal) {
        setResolutionProposal(res.resolution_proposal);
      }
    } catch (err) {
      console.error('Validation failed', err);
    } finally {
      setIsValidating(false);
    }
  }, [selectedComponents, targetOs, targetArch, targetRosDistro]);

  useEffect(() => {
    const timer = setTimeout(() => {
      runValidation();
    }, 250);
    return () => clearTimeout(timer);
  }, [runValidation]);

  const handleAddComponent = (res: Resource) => {
    if (selectedComponents.some((c) => c.resource_id === res.id)) return;

    let cat = 'general';
    if (res.type.includes('sensor') || res.capabilities?.some((c) => c.includes('sensor') || c.includes('camera') || c.includes('lidar'))) {
      cat = 'sensors';
    } else if (res.type.includes('middleware') || res.id.includes('dds')) {
      cat = 'middleware';
    } else if (res.type.includes('navigation') || res.id.includes('nav2')) {
      cat = 'navigation';
    } else if (res.type.includes('mapping') || res.id.includes('slam')) {
      cat = 'mapping';
    } else if (res.type.includes('control')) {
      cat = 'control';
    } else if (res.type.includes('simulation') || res.id.includes('gazebo')) {
      cat = 'simulation';
    }

    const newComp: StackComponent = {
      resource_id: res.id,
      version: res.version || '1.0.0',
      category: cat,
      optional: false,
    };

    setSelectedComponents((prev) => [...prev, newComp]);
    setSaveStatus('modified');
  };

  const handleRemoveComponent = (resourceId: string) => {
    setSelectedComponents((prev) => prev.filter((c) => c.resource_id !== resourceId));
    setSaveStatus('modified');
  };

  const handleApplyTemplate = (tmpl: StackTemplate) => {
    setStackName(tmpl.name);
    setStackDescription(tmpl.description);
    setRobotDomain(tmpl.robot_domain);
    setRobotType(tmpl.robot_type);
    setTargetOs(tmpl.target_os);
    setTargetArch(tmpl.target_arch);
    setTargetRosDistro(tmpl.target_ros_distro);
    setSelectedComponents(tmpl.components);
    setSaveStatus('modified');
  };

  const handleAnalyzeResolution = async () => {
    setIsResolving(true);
    try {
      const proposal = await resolveAdhocStack({
        components: selectedComponents,
        target_os: targetOs,
        target_arch: targetArch,
        target_ros_distro: targetRosDistro,
      });
      setResolutionProposal(proposal);
      setShowResolveModal(true);
    } catch (err) {
      console.error('Resolution failed', err);
    } finally {
      setIsResolving(false);
    }
  };

  const handleApplyResolution = () => {
    if (!resolutionProposal) return;
    const additions: StackComponent[] = resolutionProposal.proposed_actions
      .filter((a) => a.action === 'add_component')
      .map((a) => ({
        resource_id: a.resource_id,
        version: a.version || '1.0.0',
        category: a.category || 'general',
        optional: a.optional || false,
      }));

    setSelectedComponents((prev) => {
      const existingIds = new Set(prev.map((p) => p.resource_id));
      const filteredAdditions = additions.filter((a) => !existingIds.has(a.resource_id));
      return [...prev, ...filteredAdditions];
    });

    setShowResolveModal(false);
    setSaveStatus('modified');
  };

  const buildCurrentManifest = () => ({
    $schema: 'https://openrobo.org/schemas/v1/stack.schema.json',
    id: stackName,
    name: stackName,
    version: '1.0.0',
    description: stackDescription,
    created_at: new Date().toISOString(),
    robot: {
      domain: robotDomain,
      type: robotType,
    },
    target_platform: {
      os: targetOs,
      architecture: targetArch,
      ros_distribution: targetRosDistro,
    },
    target: {
      ros_distro: targetRosDistro,
      os: targetOs,
      architecture: targetArch,
    },
    resources: selectedComponents.map((c) => ({
      id: c.resource_id,
      name: c.resource_id.split('/').pop() || c.resource_id,
      version: c.version || '1.0.0',
    })),
    components: selectedComponents.map((c) => ({
      resource_id: c.resource_id,
      version: c.version || '1.0.0',
      category: c.category || 'general',
      optional: c.optional || false,
    })),
  });

  const handleExportManifest = () => {
    const manifest = {
      $schema: 'https://openrobo.org/schemas/v1/stack.schema.json',
      name: stackName,
      version: '1.0.0',
      description: stackDescription,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      robot: {
        domain: robotDomain,
        type: robotType,
      },
      target_platform: {
        os: targetOs,
        arch: targetArch,
        ros_distribution: targetRosDistro,
        ros_version: targetRosDistro,
      },
      components: selectedComponents,
      metadata: {
        generator: 'OpenRobo Stack Builder v0.4.0',
      },
    };

    const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${stackName || 'robot_stack'}.openrobo.stack.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportSubmit = async () => {
    setImportError(null);
    try {
      const parsed = JSON.parse(importText);
      const res = await importStackManifest(parsed);
      if (res.is_valid) {
        setStackName(parsed.name || 'imported_stack');
        if (parsed.description) setStackDescription(parsed.description);
        if (parsed.robot?.domain) setRobotDomain(parsed.robot.domain);
        if (parsed.robot?.type) setRobotType(parsed.robot.type);
        if (parsed.target_platform?.os) setTargetOs(parsed.target_platform.os);
        if (parsed.target_platform?.arch) setTargetArch(parsed.target_platform.arch);
        if (parsed.target_platform?.ros_distribution || parsed.target_platform?.ros_version) {
          setTargetRosDistro(parsed.target_platform.ros_distribution || parsed.target_platform.ros_version);
        }
        setSelectedComponents(parsed.components || []);
        setShowImportModal(false);
        setImportText('');
        setSaveStatus('modified');
      }
    } catch (err: any) {
      setImportError(err.message || 'Invalid JSON format or schema validation failed.');
    }
  };

  const handleSaveStack = async () => {
    setSaveStatus('saving');
    try {
      await createStack({
        name: stackName,
        version: '1.0.0',
        description: stackDescription,
        robot_domain: robotDomain,
        robot_type: robotType,
        target_os: targetOs,
        target_arch: targetArch,
        target_ros_distro: targetRosDistro,
        components: selectedComponents,
      });
      setSaveStatus('saved');
    } catch (err) {
      console.error('Failed to save stack', err);
      setSaveStatus('modified');
    }
  };

  const getStatusBadge = (status?: CompatibilityStatus) => {
    switch (status) {
      case 'compatible':
        return <span style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.85rem', fontWeight: 600, background: 'rgba(34,197,94,0.15)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.3)' }}>? COMPATIBLE</span>;
      case 'conditional':
        return <span style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.85rem', fontWeight: 600, background: 'rgba(234,179,8,0.15)', color: '#facc15', border: '1px solid rgba(234,179,8,0.3)' }}>? CONDITIONAL</span>;
      case 'incompatible':
        return <span style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.85rem', fontWeight: 600, background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)' }}>? INCOMPATIBLE</span>;
      default:
        return <span style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.85rem', fontWeight: 600, background: 'rgba(148,163,184,0.15)', color: '#94a3b8', border: '1px solid rgba(148,163,184,0.3)' }}>? UNKNOWN</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', overflow: 'hidden', background: 'var(--bg-primary)' }}>
      {/* Top Engineering Workspace Control Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '1.4rem' }}>???</span>
          <div>
            <input
              type="text"
              value={stackName}
              onChange={(e) => {
                setStackName(e.target.value);
                setSaveStatus('modified');
              }}
              style={{ fontSize: '1.1rem', fontWeight: 700, background: 'transparent', border: '1px solid transparent', color: 'var(--text-primary)', outline: 'none', borderBottom: '1px dashed var(--border-color)', padding: '2px 6px' }}
              placeholder="Stack Identifier"
            />
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Robotics Stack Composition Workspace
            </div>
          </div>
        </div>

        {/* Target Environment Selectors */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(0,0,0,0.2)', padding: '4px 8px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ROS:</span>
            <select
              value={targetRosDistro}
              onChange={(e) => setTargetRosDistro(e.target.value)}
              style={{ background: 'var(--bg-card)', color: 'var(--accent-cyan)', border: '1px solid var(--border-color)', borderRadius: '4px', fontSize: '0.8rem', padding: '2px 6px' }}
            >
              <option value="jazzy">ROS 2 Jazzy</option>
              <option value="humble">ROS 2 Humble</option>
              <option value="iron">ROS 2 Iron</option>
              <option value="rolling">ROS 2 Rolling</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>OS:</span>
            <select
              value={targetOs}
              onChange={(e) => setTargetOs(e.target.value)}
              style={{ background: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '4px', fontSize: '0.8rem', padding: '2px 6px' }}
            >
              <option value="ubuntu_24_04">Ubuntu 24.04</option>
              <option value="ubuntu_22_04">Ubuntu 22.04</option>
              <option value="debian_12">Debian 12</option>
              <option value="windows_11">Windows 11</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Arch:</span>
            <select
              value={targetArch}
              onChange={(e) => setTargetArch(e.target.value)}
              style={{ background: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '4px', fontSize: '0.8rem', padding: '2px 6px' }}
            >
              <option value="x86_64">x86_64</option>
              <option value="aarch64">aarch64 (ARM64)</option>
              <option value="armv7l">armv7l</option>
            </select>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <select
            onChange={(e) => {
              const tmpl = templates.find((t) => t.id === e.target.value);
              if (tmpl) handleApplyTemplate(tmpl);
            }}
            defaultValue=""
            style={{ background: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', fontSize: '0.85rem', padding: '6px 12px' }}
          >
            <option value="" disabled>Load Starter Template...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.title}</option>
            ))}
          </select>

          <button
            onClick={() => setShowImportModal(true)}
            style={{ background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '6px 12px', fontSize: '0.85rem', cursor: 'pointer' }}
          >
            ?? Import
          </button>

          <button
            onClick={handleExportManifest}
            disabled={selectedComponents.length === 0}
            style={{ background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '6px 12px', fontSize: '0.85rem', cursor: selectedComponents.length === 0 ? 'not-allowed' : 'pointer', opacity: selectedComponents.length === 0 ? 0.5 : 1 }}
          >
            ?? Export .openrobo.stack.json
          </button>

          <button
            onClick={handleSaveStack}
            style={{ background: 'var(--accent-cyan)', color: '#000', border: 'none', borderRadius: '6px', padding: '6px 14px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}
          >
            {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? '? Saved' : '?? Save Stack'}
          </button>
        </div>
      </div>

      {/* Main 3-Panel Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr 380px', flex: 1, overflow: 'hidden' }}>
        {/* LEFT PANEL: Resource Library */}
        <div style={{ display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border-color)', background: 'var(--bg-secondary)', overflow: 'hidden' }}>
          <div style={{ padding: '14px', borderBottom: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '8px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>Resource Library</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{filteredLibrary.length} available</span>
            </div>
            <input
              type="text"
              placeholder="Search components & drivers..."
              value={librarySearch}
              onChange={(e) => setLibrarySearch(e.target.value)}
              style={{ width: '100%', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '6px 10px', fontSize: '0.85rem', color: 'var(--text-primary)', outline: 'none' }}
            />
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
            {isLibraryLoading ? (
              <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading registry resources...</div>
            ) : filteredLibrary.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>No matching components found.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {filteredLibrary.map((res) => {
                  const isAdded = selectedComponents.some((c) => c.resource_id === res.id);
                  return (
                    <div
                      key={res.id}
                      style={{
                        padding: '10px',
                        background: isAdded ? 'rgba(34,211,238,0.06)' : 'var(--bg-card)',
                        border: isAdded ? '1px solid rgba(34,211,238,0.3)' : '1px solid var(--border-color)',
                        borderRadius: '6px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{res.name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{res.id}</div>
                        </div>
                        <button
                          onClick={() => isAdded ? handleRemoveComponent(res.id) : handleAddComponent(res)}
                          style={{
                            padding: '3px 8px',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            borderRadius: '4px',
                            border: 'none',
                            background: isAdded ? 'rgba(239,68,68,0.15)' : 'var(--accent-cyan)',
                            color: isAdded ? '#f87171' : '#000',
                            cursor: 'pointer',
                          }}
                        >
                          {isAdded ? 'Remove' : '+ Add'}
                        </button>
                      </div>

                      {res.summary && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.3 }}>
                          {res.summary}
                        </div>
                      )}

                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
                        <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>{res.type}</span>
                        {res.robotics_domains?.slice(0, 2).map((d) => (
                          <span key={d} style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(34,211,238,0.1)', color: 'var(--accent-cyan)' }}>{d}</span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* CENTER PANEL: Stack Pipeline Composition Area */}
        <div style={{ display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)', overflowY: 'auto' }}>
          <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>Stack Pipeline Composition</h2>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                {selectedComponents.length} components assembled in target pipeline
              </div>
            </div>

            {selectedComponents.length > 0 && (
              <button
                onClick={() => setSelectedComponents([])}
                style={{ background: 'transparent', border: '1px solid rgba(239,68,68,0.3)', color: '#f87171', padding: '4px 10px', borderRadius: '4px', fontSize: '0.75rem', cursor: 'pointer' }}
              >
                Clear Stack
              </button>
            )}
          </div>

          <div style={{ flex: 1, padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {selectedComponents.length === 0 ? (
              <div style={{ border: '2px dashed var(--border-color)', borderRadius: '12px', padding: '48px', textAlign: 'center', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '2.5rem' }}>??</span>
                <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>Your Robotics Stack is Empty</div>
                <div style={{ fontSize: '0.85rem', maxWidth: '400px', lineHeight: 1.4 }}>
                  Select packages and drivers from the Resource Library on the left or load a starter template above to assemble your complete robot stack.
                </div>
              </div>
            ) : (
              CATEGORIES.map((cat) => {
                const catComponents = selectedComponents.filter((c) => (c.category || 'general') === cat.id);
                if (catComponents.length === 0) return null;

                return (
                  <div key={cat.id} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      <span>{cat.icon}</span>
                      <span>{cat.label}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>({catComponents.length})</span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {catComponents.map((comp) => {
                        const resInfo = availableResources.find((r) => r.id === comp.resource_id);
                        return (
                          <div
                            key={comp.resource_id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              background: 'var(--bg-secondary)',
                              border: '1px solid var(--border-color)',
                              borderRadius: '6px',
                              padding: '8px 12px',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <span style={{ color: 'var(--accent-cyan)', fontSize: '0.85rem' }}>?</span>
                              <div>
                                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                  {resInfo?.name || comp.resource_id}
                                </div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                                  {comp.resource_id}
                                </div>
                              </div>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>v:</span>
                                <input
                                  type="text"
                                  value={comp.version || '1.0.0'}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    setSelectedComponents((prev) =>
                                      prev.map((c) => (c.resource_id === comp.resource_id ? { ...c, version: val } : c))
                                    );
                                  }}
                                  style={{ width: '60px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '2px 4px', fontSize: '0.75rem', color: 'var(--text-primary)', textAlign: 'center' }}
                                />
                              </div>

                              <button
                                onClick={() => handleRemoveComponent(comp.resource_id)}
                                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1rem', padding: '2px 6px' }}
                                title="Remove from stack"
                              >
                                ?
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT PANEL: Live Compatibility & Stack Inspector */}
        <div style={{ display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--border-color)', background: 'var(--bg-secondary)', overflow: 'hidden' }}>
          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', background: 'var(--bg-card)' }}>
            <button
              onClick={() => setActiveTab('diagnostics')}
              style={{ flex: 1, padding: '10px', fontSize: '0.8rem', fontWeight: 600, background: activeTab === 'diagnostics' ? 'var(--bg-secondary)' : 'transparent', color: activeTab === 'diagnostics' ? 'var(--accent-cyan)' : 'var(--text-muted)', border: 'none', borderBottom: activeTab === 'diagnostics' ? '2px solid var(--accent-cyan)' : 'none', cursor: 'pointer' }}
            >
              Health & Rules
            </button>
            <button
              onClick={() => setActiveTab('graph')}
              style={{ flex: 1, padding: '10px', fontSize: '0.8rem', fontWeight: 600, background: activeTab === 'graph' ? 'var(--bg-secondary)' : 'transparent', color: activeTab === 'graph' ? 'var(--accent-cyan)' : 'var(--text-muted)', border: 'none', borderBottom: activeTab === 'graph' ? '2px solid var(--accent-cyan)' : 'none', cursor: 'pointer' }}
            >
              Stack Graph
            </button>
            <button
              onClick={() => setActiveTab('manifest')}
              style={{ flex: 1, padding: '10px', fontSize: '0.8rem', fontWeight: 600, background: activeTab === 'manifest' ? 'var(--bg-secondary)' : 'transparent', color: activeTab === 'manifest' ? 'var(--accent-cyan)' : 'var(--text-muted)', border: 'none', borderBottom: activeTab === 'manifest' ? '2px solid var(--accent-cyan)' : 'none', cursor: 'pointer' }}
            >
              Manifest JSON
            </button>
          </div>

          {/* Tab Content */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
            {activeTab === 'diagnostics' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Health Summary Card */}
                <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>Stack Health Status</span>
                    {getStatusBadge(validationResult?.status)}
                  </div>

                  {validationResult && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', marginTop: '4px' }}>
                      <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '4px', fontSize: '0.75rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Compatible: </span>
                        <strong style={{ color: '#4ade80' }}>{validationResult.verified_compatible_count}</strong>
                      </div>
                      <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '4px', fontSize: '0.75rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Conditional: </span>
                        <strong style={{ color: '#facc15' }}>{validationResult.conditional_count}</strong>
                      </div>
                      <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '4px', fontSize: '0.75rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Incompatible: </span>
                        <strong style={{ color: '#f87171' }}>{validationResult.incompatible_count}</strong>
                      </div>
                      <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '4px', fontSize: '0.75rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Missing Deps: </span>
                        <strong style={{ color: validationResult.missing_dependencies_count > 0 ? '#facc15' : 'var(--text-primary)' }}>{validationResult.missing_dependencies_count}</strong>
                      </div>
                    </div>
                  )}
                </div>

                {/* Auto-Resolve Banner if Missing Deps Exist */}
                {validationResult && validationResult.missing_dependencies_count > 0 && (
                  <div style={{ background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.3)', borderRadius: '8px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#facc15', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span>??</span>
                      <span>Missing Dependencies Detected</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.3 }}>
                      The stack requires {validationResult.missing_dependencies_count} additional components to satisfy dependency relationships.
                    </div>
                    <button
                      onClick={handleAnalyzeResolution}
                      disabled={isResolving}
                      style={{ background: '#facc15', color: '#000', border: 'none', borderRadius: '4px', padding: '6px 10px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', alignSelf: 'flex-start' }}
                    >
                      {isResolving ? 'Analyzing...' : 'Resolve Dependencies'}
                    </button>
                  </div>
                )}

                {/* Diagnostic Rule Evaluations */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>Rule Diagnostic Logs</div>
                  {isValidating ? (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textAlign: 'center', padding: '12px' }}>Evaluating compatibility rules...</div>
                  ) : !validationResult || validationResult.compatibility_result.rule_evaluations.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textAlign: 'center', padding: '12px' }}>No rules evaluated yet.</div>
                  ) : (
                    validationResult.compatibility_result.rule_evaluations.map((ev, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: 'var(--bg-card)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '6px',
                          padding: '8px 10px',
                          fontSize: '0.75rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong style={{ color: 'var(--text-primary)' }}>{ev.rule_name}</strong>
                          <span style={{ color: ev.status === 'compatible' ? '#4ade80' : ev.status === 'incompatible' ? '#f87171' : '#facc15' }}>
                            {ev.status.toUpperCase()}
                          </span>
                        </div>
                        <div style={{ color: 'var(--text-secondary)' }}>{ev.message}</div>
                        {ev.remediation && (
                          <div style={{ color: 'var(--accent-cyan)', fontSize: '0.7rem' }}>
                            ?? {ev.remediation}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {activeTab === 'graph' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>Component Relationships</div>
                {selectedComponents.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textAlign: 'center', padding: '24px' }}>Add components to view graph connections.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {selectedComponents.map((c) => (
                      <div key={c.resource_id} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '10px' }}>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>{c.resource_id}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                          Category: {c.category} ? Target ROS: {targetRosDistro}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'manifest' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>Canonical Manifest</span>
                  <button
                    onClick={() => {
                      const manifest = {
                        $schema: 'https://openrobo.org/schemas/v1/stack.schema.json',
                        name: stackName,
                        version: '1.0.0',
                        description: stackDescription,
                        robot: { domain: robotDomain, type: robotType },
                        target_platform: { os: targetOs, arch: targetArch, ros_distribution: targetRosDistro },
                        components: selectedComponents,
                      };
                      navigator.clipboard.writeText(JSON.stringify(manifest, null, 2));
                    }}
                    style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem', cursor: 'pointer' }}
                  >
                    Copy JSON
                  </button>
                </div>
                <pre style={{ background: '#090d16', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '12px', fontSize: '0.7rem', color: '#a5f3fc', overflowX: 'auto', maxHeight: '400px' }}>
                  {JSON.stringify(
                    {
                      $schema: 'https://openrobo.org/schemas/v1/stack.schema.json',
                      name: stackName,
                      version: '1.0.0',
                      description: stackDescription,
                      robot: { domain: robotDomain, type: robotType },
                      target_platform: { os: targetOs, arch: targetArch, ros_distribution: targetRosDistro },
                      components: selectedComponents,
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* RESOLUTION PROPOSAL MODAL */}
      {showResolveModal && resolutionProposal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', width: '100%', maxWidth: '600px', maxHeight: '80vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>Dependency Resolution Proposal</div>
              <button onClick={() => setShowResolveModal(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}>?</button>
            </div>

            <div style={{ padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {resolutionProposal.summary}
              </div>

              {resolutionProposal.proposed_actions.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
                    Proposed Additions ({resolutionProposal.proposed_actions.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {resolutionProposal.proposed_actions.map((act, i) => (
                      <div key={i} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>{act.name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{act.reason}</div>
                        </div>
                        <span style={{ fontSize: '0.75rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(34,197,94,0.1)', color: '#4ade80' }}>
                          + ADD
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {resolutionProposal.conflicts.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f87171', marginBottom: '8px' }}>
                    Detected Conflicts ({resolutionProposal.conflicts.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {resolutionProposal.conflicts.map((conf, i) => (
                      <div key={i} style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', padding: '8px 12px' }}>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f87171' }}>{conf.conflict_type}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>{conf.message}</div>
                        {conf.remediation && (
                          <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', marginTop: '4px' }}>?? {conf.remediation}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-color)', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setShowResolveModal(false)}
                style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '6px 14px', borderRadius: '6px', fontSize: '0.85rem', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleApplyResolution}
                style={{ background: 'var(--accent-cyan)', color: '#000', border: 'none', padding: '6px 16px', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}
              >
                Apply Proposed Changes
              </button>
            </div>
          </div>
        </div>
      )}

            {/* WORKSPACE PREVIEW MODAL */}
      <WorkspaceModal
        isOpen={showWorkspaceModal}
        onClose={() => setShowWorkspaceModal(false)}
        manifest={buildCurrentManifest()}
        stackName={stackName}
      />

      {/* IMPORT MANIFEST MODAL */}
      {showImportModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', width: '100%', maxWidth: '600px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>Import Stack Manifest</div>
              <button onClick={() => setShowImportModal(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}>?</button>
            </div>

            <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Paste the contents of a <code style={{ color: 'var(--accent-cyan)' }}>.openrobo.stack.json</code> manifest below:
              </div>

              <textarea
                rows={10}
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder='{\n  "name": "my_robot_stack",\n  "version": "1.0.0",\n  "robot": { "domain": "mobile_robotics", "type": "amr" },\n  "components": [\n    { "resource_id": "ros-navigation/nav2", "version": "1.3.0" }\n  ]\n}'
                style={{ width: '100%', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '10px', fontSize: '0.8rem', color: 'var(--text-primary)', fontFamily: 'monospace', outline: 'none' }}
              />

              {importError && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', padding: '8px 12px', color: '#f87171', fontSize: '0.8rem' }}>
                  {importError}
                </div>
              )}
            </div>

            <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-color)', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setShowImportModal(false)}
                style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '6px 14px', borderRadius: '6px', fontSize: '0.85rem', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleImportSubmit}
                disabled={!importText.trim()}
                style={{ background: 'var(--accent-cyan)', color: '#000', border: 'none', padding: '6px 16px', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 600, cursor: !importText.trim() ? 'not-allowed' : 'pointer', opacity: !importText.trim() ? 0.5 : 1 }}
              >
                Import & Validate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
