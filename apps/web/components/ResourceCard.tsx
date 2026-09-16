'use client';

import React from 'react';
import { Resource } from '../lib/api/types';

interface ResourceCardProps {
  resource: Resource;
  onSelect: (resource: Resource) => void;
}

export function getTypeBadgeClass(type: string): string {
  switch (type) {
    case 'ros_package':
      return 'badge-ros';
    case 'driver':
    case 'sensor':
    case 'actuator':
      return 'badge-driver';
    case 'robot':
      return 'badge-robot';
    case 'simulation':
      return 'badge-simulation';
    case 'tool':
    case 'protocol':
      return 'badge-tool';
    case 'framework':
    case 'library':
      return 'badge-framework';
    default:
      return 'badge-license';
  }
}

export default function ResourceCard({ resource, onSelect }: ResourceCardProps) {
  const osList = resource.platforms?.operating_systems || [];
  const rosList = resource.platforms?.ros_versions || [];
  const archList = resource.platforms?.cpu_architectures || [];

  return (
    <article
      onClick={() => onSelect(resource)}
      style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '1.25rem',
        cursor: 'pointer',
        transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '1rem',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--accent-cyan)';
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.background = 'var(--card-hover)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--border-color)';
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.background = 'var(--card-bg)';
      }}
      data-testid={`resource-card-${resource.id}`}
    >
      <div>
        {/* Top Header: ID & Type */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--accent-cyan)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {resource.id}
          </span>
          <span className={`badge ${getTypeBadgeClass(resource.type)}`}>
            {resource.type.replace('_', ' ')}
          </span>
        </div>

        {/* Resource Title */}
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.35rem', letterSpacing: '-0.01em' }}>
          {resource.name}
          {resource.version && (
            <span style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-dim)', marginLeft: '0.5rem', fontFamily: 'var(--font-mono)' }}>
              v{resource.version}
            </span>
          )}
        </h3>

        {/* Summary */}
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.45', marginBottom: '0.75rem', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {resource.summary || resource.description || 'No description provided.'}
        </p>

        {/* Domains & Capabilities */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginBottom: '0.75rem' }}>
          {resource.robotics_domains?.map((dom) => (
            <span
              key={dom}
              style={{
                fontSize: '0.75rem',
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                color: '#cbd5e1',
                borderRadius: '4px',
                padding: '0.15rem 0.45rem',
                fontFamily: 'var(--font-mono)',
              }}
            >
              #{dom}
            </span>
          ))}
          {resource.capabilities?.slice(0, 3).map((cap) => (
            <span
              key={cap}
              style={{
                fontSize: '0.75rem',
                background: 'rgba(51, 65, 85, 0.4)',
                color: 'var(--text-dim)',
                borderRadius: '4px',
                padding: '0.15rem 0.45rem',
              }}
            >
              {cap}
            </span>
          ))}
        </div>
      </div>

      {/* Card Footer: Metadata & Platform badges */}
      <div style={{ borderTop: '1px solid rgba(30, 41, 59, 0.8)', paddingTop: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          {resource.spdx_license_id && (
            <span className="badge badge-license">
              {resource.spdx_license_id}
            </span>
          )}
          {resource.evidence_level && (
            <span className="badge badge-evidence">
              ● {resource.evidence_level.replace('_', ' ')}
            </span>
          )}
        </div>

        {/* Platform tags */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          {rosList.length > 0 && (
            <span>ROS 2: {rosList.join(', ')}</span>
          )}
          {rosList.length === 0 && osList.length > 0 && (
            <span>{osList[0]}</span>
          )}
        </div>
      </div>
    </article>
  );
}
