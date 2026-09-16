'use client';

import React from 'react';
import { SearchFacetDistribution } from '../lib/api/types';

interface SearchAndFiltersProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedType: string;
  onTypeChange: (type: string) => void;
  selectedDomain: string;
  onDomainChange: (domain: string) => void;
  selectedEcosystem: string;
  onEcosystemChange: (ecosystem: string) => void;
  facets?: SearchFacetDistribution | null;
  totalResults: number;
  onReset: () => void;
}

const TYPE_OPTIONS = [
  { label: 'All Types', value: '' },
  { label: 'ROS Packages', value: 'ros_package' },
  { label: 'Drivers', value: 'driver' },
  { label: 'Sensors', value: 'sensor' },
  { label: 'Robots', value: 'robot' },
  { label: 'Simulation', value: 'simulation' },
  { label: 'Tools', value: 'tool' },
  { label: 'Frameworks', value: 'framework' },
  { label: 'Protocols', value: 'protocol' },
];

const DOMAIN_OPTIONS = [
  { label: 'All Domains', value: '' },
  { label: 'Navigation', value: 'navigation' },
  { label: 'Manipulation', value: 'manipulation' },
  { label: 'Perception', value: 'perception' },
  { label: 'Mapping & SLAM', value: 'mapping' },
  { label: 'Control', value: 'control' },
  { label: 'Simulation', value: 'simulation' },
  { label: 'Embedded', value: 'embedded' },
  { label: 'Telemetry', value: 'telemetry' },
];

const ECOSYSTEM_OPTIONS = [
  { label: 'All Ecosystems', value: '' },
  { label: 'ROS 2 Jazzy', value: 'Jazzy' },
  { label: 'ROS 2 Humble', value: 'Humble' },
  { label: 'Linux (Ubuntu)', value: 'Ubuntu' },
  { label: 'Windows', value: 'Windows' },
  { label: 'macOS', value: 'macOS' },
];

export default function SearchAndFilters({
  searchQuery,
  onSearchChange,
  selectedType,
  onTypeChange,
  selectedDomain,
  onDomainChange,
  selectedEcosystem,
  onEcosystemChange,
  facets,
  totalResults,
  onReset,
}: SearchAndFiltersProps) {
  const hasActiveFilters = Boolean(searchQuery || selectedType || selectedDomain || selectedEcosystem);

  return (
    <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem', marginBottom: '1.5rem' }}>
      {/* Search Input Bar */}
      <div style={{ position: 'relative', marginBottom: '1.25rem' }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search robotics packages, drivers, algorithms, hardware, or capabilities (e.g. Nav2, LiDAR, SLAM, Jazzy)..."
          style={{
            width: '100%',
            background: 'var(--bg-color)',
            border: '1px solid var(--border-color)',
            borderRadius: '6px',
            padding: '0.75rem 1rem',
            paddingLeft: '2.75rem',
            color: 'var(--text-main)',
            fontSize: '0.95rem',
            outline: 'none',
            transition: 'border-color 0.15s ease',
          }}
          onFocus={(e) => (e.target.style.borderColor = 'var(--accent-cyan)')}
          onBlur={(e) => (e.target.style.borderColor = 'var(--border-color)')}
          data-testid="search-input"
        />
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ position: 'absolute', left: '0.9rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }}
        >
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>

        {searchQuery && (
          <button
            onClick={() => onSearchChange('')}
            style={{
              position: 'absolute',
              right: '0.75rem',
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'transparent',
              border: 'none',
              color: 'var(--text-dim)',
              fontSize: '0.85rem',
              padding: '0.25rem 0.5rem',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Type Filter Buttons with Dynamic Facet Counts */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontWeight: 600, marginRight: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Type:
        </span>
        {TYPE_OPTIONS.map((opt) => {
          const count = opt.value ? facets?.types?.[opt.value] : totalResults;
          return (
            <button
              key={opt.value}
              onClick={() => onTypeChange(opt.value)}
              style={{
                background: selectedType === opt.value ? 'var(--accent-cyan-glow)' : 'rgba(15, 23, 42, 0.5)',
                border: `1px solid ${selectedType === opt.value ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                color: selectedType === opt.value ? 'var(--accent-cyan)' : 'var(--text-muted)',
                borderRadius: '4px',
                padding: '0.3rem 0.65rem',
                fontSize: '0.8rem',
                fontWeight: 500,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              data-testid={`filter-type-${opt.value || 'all'}`}
            >
              <span>{opt.label}</span>
              {count !== undefined && count > 0 && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    background: selectedType === opt.value ? 'var(--accent-cyan)' : 'rgba(51, 65, 85, 0.6)',
                    color: selectedType === opt.value ? '#090d16' : 'var(--text-dim)',
                    padding: '0.05rem 0.3rem',
                    borderRadius: '10px',
                    fontWeight: 600,
                  }}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Domain & Ecosystem Dropdowns */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(30, 41, 59, 0.6)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label htmlFor="domain-select" style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontWeight: 600 }}>
              Domain:
            </label>
            <select
              id="domain-select"
              value={selectedDomain}
              onChange={(e) => onDomainChange(e.target.value)}
              style={{
                background: 'var(--bg-color)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-main)',
                borderRadius: '4px',
                padding: '0.35rem 0.6rem',
                fontSize: '0.85rem',
                outline: 'none',
              }}
              data-testid="domain-select"
            >
              {DOMAIN_OPTIONS.map((d) => {
                const count = d.value ? facets?.domains?.[d.value] : undefined;
                return (
                  <option key={d.value} value={d.value}>
                    {d.label} {count !== undefined ? `(${count})` : ''}
                  </option>
                );
              })}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label htmlFor="ecosystem-select" style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontWeight: 600 }}>
              Ecosystem:
            </label>
            <select
              id="ecosystem-select"
              value={selectedEcosystem}
              onChange={(e) => onEcosystemChange(e.target.value)}
              style={{
                background: 'var(--bg-color)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-main)',
                borderRadius: '4px',
                padding: '0.35rem 0.6rem',
                fontSize: '0.85rem',
                outline: 'none',
              }}
              data-testid="ecosystem-select"
            >
              {ECOSYSTEM_OPTIONS.map((e) => (
                <option key={e.value} value={e.value}>
                  {e.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            <strong>{totalResults}</strong> {totalResults === 1 ? 'resource' : 'resources'} matched
          </span>

          {hasActiveFilters && (
            <button
              onClick={onReset}
              style={{
                background: 'transparent',
                border: '1px solid var(--border-color)',
                color: 'var(--accent-cyan)',
                borderRadius: '4px',
                padding: '0.3rem 0.65rem',
                fontSize: '0.8rem',
                cursor: 'pointer',
              }}
              data-testid="reset-filters"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
