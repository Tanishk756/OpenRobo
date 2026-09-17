'use client';

import React from 'react';
import { Resource } from '../lib/api/types';

interface ResourceDetailDrawerProps {
  resource: Resource | null;
  onClose: () => void;
}

export function ResourceDetailDrawer({ resource, onClose }: ResourceDetailDrawerProps) {
  if (!resource) return null;

  const rosList = resource.platforms?.ros_versions || [];
  const osList = resource.platforms?.operating_systems || [];
  const archList = resource.platforms?.cpu_architectures || [];
  const repoUrl = resource.source?.repo_url || resource.repo_url;
  const provenance = resource.metadata_json?.provenance;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Resource Details"
      data-testid="detail-drawer"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        justifyContent: 'flex-end',
        background: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '620px',
          background: 'var(--panel-bg)',
          borderLeft: '1px solid var(--border-color)',
          height: '100%',
          overflowY: 'auto',
          padding: '2rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.5rem',
          boxShadow: '-10px 0 30px rgba(0, 0, 0, 0.5)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.35rem' }}>
              <span className="badge badge-type">{resource.type}</span>
              {resource.version && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                  v{resource.version}
                </span>
              )}
            </div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-main)' }}>{resource.name}</h2>
            <code style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>{resource.id}</code>
          </div>
          <button
            onClick={onClose}
            aria-label="Close drawer"
            data-testid="close-drawer"
            style={{
              background: 'transparent',
              border: '1px solid var(--border-color)',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              padding: '0.4rem 0.7rem',
              borderRadius: '4px',
              fontSize: '1rem',
            }}
          >
            ✕
          </button>
        </div>

        {/* Overview */}
        <section>
          <h3 style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
            Overview
          </h3>
          <p style={{ color: 'var(--text-main)', fontSize: '0.95rem', lineHeight: '1.6', marginBottom: '0.75rem' }}>
            {resource.summary || 'No summary available.'}
          </p>
          {resource.description && resource.description !== resource.summary && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: '1.5' }}>
              {resource.description}
            </p>
          )}
        </section>

        {/* Source Repository */}
        {repoUrl && (
          <section style={{ background: 'var(--bg-color)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '1rem' }}>
            <h3 style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.35rem' }}>
              Upstream Source
            </h3>
            <a
              href={repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"></path>
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
            <span className="badge badge-evidence">🔒 {resource.evidence_level?.replace('_', ' ')}</span>
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
