'use client';

import React, { useEffect, useState } from 'react';
import {
  evaluateCompatibility,
  fetchResourceCompatibilityProfile,
} from '../lib/api/client';
import {
  CompatibilityResult,
  Resource,
  ResourceCompatibilityProfile,
} from '../lib/api/types';

interface ResourceDetailDrawerProps {
  resource: Resource | null;
  isOpen?: boolean;
  onClose: () => void;
}

export function ResourceDetailDrawer({
  resource,
  isOpen = true,
  onClose,
}: ResourceDetailDrawerProps) {
  const isDrawerOpen = isOpen && Boolean(resource);
  const [profile, setProfile] = useState<ResourceCompatibilityProfile | null>(null);
  const [targetRos, setTargetRos] = useState<string>('Jazzy');
  const [targetOs, setTargetOs] = useState<string>('Ubuntu');
  const [targetArch, setTargetArch] = useState<string>('x86_64');
  const [compatResult, setCompatResult] = useState<CompatibilityResult | null>(null);

  useEffect(() => {
    if (resource && isDrawerOpen) {
      fetchResourceCompatibilityProfile(resource.id)
        .then((res) => setProfile(res))
        .catch(() => setProfile(null));
    } else {
      setProfile(null);
      setCompatResult(null);
    }
  }, [resource, isDrawerOpen]);

  useEffect(() => {
    if (resource && isDrawerOpen) {
      evaluateCompatibility([resource.id], {
        ros_version: targetRos,
        os: targetOs,
        cpu_architecture: targetArch,
      })
        .then((res) => setCompatResult(res))
        .catch(() => setCompatResult(null));
    }
  }, [resource, isDrawerOpen, targetRos, targetOs, targetArch]);

  if (!isDrawerOpen || !resource) return null;

  const rosList = resource.platforms?.ros_versions || [];
  const osList = resource.platforms?.operating_systems || [];
  const archList = resource.platforms?.cpu_architectures || [];
  const repoUrl = resource.repo_url || resource.source?.repo_url;
  const provenance = resource.metadata_json?.provenance;

  const getStatusBadgeStyle = (status?: string) => {
    switch (status) {
      case 'compatible':
        return { bg: 'rgba(34, 197, 94, 0.15)', border: 'rgba(34, 197, 94, 0.4)', color: '#4ade80', icon: '?', text: 'COMPATIBLE' };
      case 'conditional':
        return { bg: 'rgba(234, 179, 8, 0.15)', border: 'rgba(234, 179, 8, 0.4)', color: '#facc15', icon: '?', text: 'CONDITIONAL' };
      case 'incompatible':
        return { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.4)', color: '#f87171', icon: '?', text: 'INCOMPATIBLE' };
      default:
        return { bg: 'rgba(148, 163, 184, 0.15)', border: 'rgba(148, 163, 184, 0.4)', color: '#cbd5e1', icon: '?', text: 'UNKNOWN' };
    }
  };

  const badgeInfo = getStatusBadgeStyle(compatResult?.status);

  return (
    <div
      data-testid="detail-drawer"
      role="dialog"
      aria-modal="true"
      aria-label={`Details for ${resource.name}`}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        justifyContent: 'flex-end',
        background: 'rgba(5, 7, 15, 0.65)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '680px',
          height: '100%',
          background: 'var(--card-bg)',
          borderLeft: '1px solid var(--border-color)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '-10px 0 30px rgba(0,0,0,0.5)',
          overflowY: 'auto',
          padding: '1.75rem',
          gap: '1.25rem',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <span className="badge badge-type">{resource.type}</span>
              {resource.version && (
                <span style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                  v{resource.version}
                </span>
              )}
            </div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.4rem', fontFamily: 'var(--font-heading)' }}>
              {resource.name}
            </h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: '0.1rem' }}>
              {resource.id}
            </p>
          </div>
          <button
            data-testid="close-drawer"
            onClick={onClose}
            aria-label="Close details"
            style={{
              background: 'transparent',
              border: '1px solid var(--border-color)',
              color: 'var(--text-dim)',
              borderRadius: '6px',
              padding: '0.4rem 0.75rem',
              cursor: 'pointer',
              fontSize: '1rem',
            }}
          >
            ?
          </button>
        </div>

        {/* Compatibility Reasoning Layer */}
        <section data-testid="compatibility-section" style={{ background: '#0a0f1d', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <h3 style={{ fontSize: '0.9rem', color: '#67e8f9', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Compatibility Intelligence
            </h3>
            <span
              data-testid="compatibility-badge"
              style={{
                background: badgeInfo.bg,
                border: `1px solid ${badgeInfo.border}`,
                color: badgeInfo.color,
                padding: '0.2rem 0.6rem',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
              }}
            >
              <span>{badgeInfo.icon}</span>
              <span>{badgeInfo.text}</span>
            </span>
          </div>

          {/* Target Environment Evaluator Form */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <div>
              <label style={{ fontSize: '0.7rem', color: 'var(--text-dim)', display: 'block', marginBottom: '0.2rem' }}>Target ROS</label>
              <select
                value={targetRos}
                onChange={(e) => setTargetRos(e.target.value)}
                style={{ width: '100%', background: '#05070f', border: '1px solid #334155', color: '#f8fafc', padding: '0.35rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem' }}
              >
                <option value="Jazzy">ROS 2 Jazzy</option>
                <option value="Humble">ROS 2 Humble</option>
                <option value="Iron">ROS 2 Iron</option>
                <option value="Rolling">ROS 2 Rolling</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: '0.7rem', color: 'var(--text-dim)', display: 'block', marginBottom: '0.2rem' }}>Target OS</label>
              <select
                value={targetOs}
                onChange={(e) => setTargetOs(e.target.value)}
                style={{ width: '100%', background: '#05070f', border: '1px solid #334155', color: '#f8fafc', padding: '0.35rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem' }}
              >
                <option value="Ubuntu">Ubuntu Linux</option>
                <option value="Windows">Windows</option>
                <option value="macOS">macOS</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: '0.7rem', color: 'var(--text-dim)', display: 'block', marginBottom: '0.2rem' }}>CPU Arch</label>
              <select
                value={targetArch}
                onChange={(e) => setTargetArch(e.target.value)}
                style={{ width: '100%', background: '#05070f', border: '1px solid #334155', color: '#f8fafc', padding: '0.35rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem' }}
              >
                <option value="x86_64">x86_64 (AMD64)</option>
                <option value="aarch64">aarch64 (ARM64)</option>
                <option value="armv7l">armv7l</option>
              </select>
            </div>
          </div>

          {/* Live Evaluation Diagnostics */}
          {compatResult && compatResult.conflicts && compatResult.conflicts.length > 0 && (
            <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '6px', padding: '0.65rem 0.75rem', marginBottom: '0.75rem' }}>
              <h4 style={{ fontSize: '0.75rem', color: '#f87171', fontWeight: 600, marginBottom: '0.25rem' }}>
                Conflict Diagnostics ({compatResult.conflicts.length})
              </h4>
              {compatResult.conflicts.map((conf, idx) => (
                <div key={idx} style={{ fontSize: '0.75rem', color: '#fca5a5', marginTop: '0.25rem' }}>
                  ? {conf.message}
                  {conf.remediation && (
                    <div style={{ color: '#93c5fd', fontSize: '0.7rem', marginTop: '0.15rem', paddingLeft: '0.75rem' }}>
                      ? Suggestion: {conf.remediation}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Graph Relationships & Evidence */}
          {profile && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem', fontSize: '0.75rem' }}>
              <div style={{ background: '#05070f', padding: '0.5rem', borderRadius: '4px', border: '1px solid #1e293b' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', marginBottom: '0.2rem' }}>Tested With</span>
                <span style={{ color: '#67e8f9', fontFamily: 'var(--font-mono)' }}>
                  {profile.tested_with?.length ? profile.tested_with.join(', ') : 'None documented'}
                </span>
              </div>
              <div style={{ background: '#05070f', padding: '0.5rem', borderRadius: '4px', border: '1px solid #1e293b' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', marginBottom: '0.2rem' }}>Compatible With</span>
                <span style={{ color: '#4ade80', fontFamily: 'var(--font-mono)' }}>
                  {profile.compatible_with?.length ? profile.compatible_with.join(', ') : 'None documented'}
                </span>
              </div>
              <div style={{ background: '#05070f', padding: '0.5rem', borderRadius: '4px', border: '1px solid #1e293b' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', marginBottom: '0.2rem' }}>Direct Dependencies</span>
                <span style={{ color: '#93c5fd', fontFamily: 'var(--font-mono)' }}>
                  {profile.direct_dependencies?.length ? profile.direct_dependencies.join(', ') : 'None (Independent)'}
                </span>
              </div>
              <div style={{ background: '#05070f', padding: '0.5rem', borderRadius: '4px', border: '1px solid #1e293b' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', marginBottom: '0.2rem' }}>Known Conflicts</span>
                <span style={{ color: profile.conflicts_with?.length ? '#f87171' : 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                  {profile.conflicts_with?.length ? profile.conflicts_with.join(', ') : 'None known'}
                </span>
              </div>
            </div>
          )}
        </section>

        {/* Description & Summary */}
        <section>
          <h3 style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
            Description
          </h3>
          <p style={{ fontSize: '0.9rem', lineHeight: '1.6', color: 'var(--text-main)' }}>
            {resource.description || resource.summary || 'No detailed description available.'}
          </p>
        </section>

        {/* Repository Link */}
        {repoUrl && (
          <section>
            <h3 style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
              Source Repository
            </h3>
            <a
              href={repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                color: 'var(--accent-cyan)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.85rem',
                textDecoration: 'none',
                background: 'var(--bg-color)',
                border: '1px solid var(--border-color)',
                padding: '0.5rem 0.75rem',
                borderRadius: '6px',
                wordBreak: 'break-all',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
              </svg>
              <span>{repoUrl}</span>
            </a>
          </section>
        )}

        {/* Provenance & Lineage */}
        {provenance && (
          <section data-testid="provenance-section" style={{ background: 'var(--bg-color)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '1rem' }}>
            <h3 style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.75rem' }}>
              Data Provenance & Ingestion Lineage
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.6rem', fontSize: '0.85rem' }}>
              <div>
                <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Provider</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>{provenance.source_provider || 'GitHub'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Revision</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>{(provenance.upstream_revision || 'HEAD').slice(0, 10)}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Classification</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: '#67e8f9' }}>{provenance.provenance_classification || 'UPSTREAM_DATA'}</span>
              </div>
              {provenance.source_manifest_path && (
                <div>
                  <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Manifest</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>{provenance.source_manifest_path}</span>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Platform Compatibility Matrix */}
        <section>
          <h3 style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
            Platform Matrix
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
            <div style={{ background: 'var(--bg-color)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.75rem' }}>
              <h4 style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>ROS Versions</h4>
              <p style={{ marginTop: '0.35rem', fontSize: '0.9rem', color: rosList.length ? 'var(--text-main)' : 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {rosList.length ? rosList.join(', ') : 'Not Specified'}
              </p>
            </div>
            <div style={{ background: 'var(--bg-color)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.75rem' }}>
              <h4 style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>Operating Systems</h4>
              <p style={{ marginTop: '0.35rem', fontSize: '0.9rem', color: osList.length ? 'var(--text-main)' : 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {osList.length ? osList.join(', ') : 'Not Specified'}
              </p>
            </div>
            <div style={{ background: 'var(--bg-color)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.75rem' }}>
              <h4 style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>Architectures</h4>
              <p style={{ marginTop: '0.35rem', fontSize: '0.9rem', color: archList.length ? 'var(--text-main)' : 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {archList.length ? archList.join(', ') : 'Not Specified'}
              </p>
            </div>
          </div>
        </section>

        {/* Capabilities */}
        {resource.capabilities && resource.capabilities.length > 0 && (
          <section>
            <h3 style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
              Robotics Capabilities
            </h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {resource.capabilities.map((cap) => (
                <span
                  key={cap}
                  style={{
                    background: 'rgba(59, 130, 246, 0.12)',
                    border: '1px solid rgba(59, 130, 246, 0.3)',
                    color: '#93c5fd',
                    borderRadius: '4px',
                    padding: '0.25rem 0.6rem',
                    fontSize: '0.8rem',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {cap}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Domains */}
        {resource.robotics_domains && resource.robotics_domains.length > 0 && (
          <section>
            <h3 style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
              Robotics Domains
            </h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {resource.robotics_domains.map((dom) => (
                <span
                  key={dom}
                  style={{
                    background: 'rgba(6, 182, 212, 0.12)',
                    border: '1px solid rgba(6, 182, 212, 0.3)',
                    color: '#67e8f9',
                    borderRadius: '4px',
                    padding: '0.25rem 0.6rem',
                    fontSize: '0.8rem',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  #{dom}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Governance & Evidence */}
        <section style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>SPDX License: </span>
            <strong style={{ fontSize: '0.85rem', color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>{resource.spdx_license_id}</strong>
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Evidence Level: </span>
            <span className="badge badge-evidence">??? {resource.evidence_level?.replace('_', ' ')}</span>
          </div>
        </section>

        {/* CLI Snippet */}
        <section style={{ background: 'var(--bg-color)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '1rem' }}>
          <h4 style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.5rem' }}>
            OpenRobo CLI Verification
          </h4>
          <pre style={{ background: '#070a11', padding: '0.65rem 0.85rem', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', overflowX: 'auto' }}>
            openrobo validate samples/{resource.id.split('/')[1] || 'manifest'}.resource.json
          </pre>
        </section>
      </div>
    </div>
  );
}

export default ResourceDetailDrawer;
