'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Navbar from '../../components/Navbar';
import ResourceCard from '../../components/ResourceCard';
import ResourceDetailDrawer from '../../components/ResourceDetailDrawer';
import SearchAndFilters from '../../components/SearchAndFilters';
import { fetchResources, ApiError } from '../../lib/api/client';
import { Resource } from '../../lib/api/types';

export default function ResourcesPage() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [selectedEcosystem, setSelectedEcosystem] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);

  const loadResources = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchResources({
        q: searchQuery,
        type: selectedType,
        domain: selectedDomain,
        ecosystem: selectedEcosystem,
        limit: 50,
      });
      setResources(result.items);
      setTotal(result.total);
    } catch (err: any) {
      setError(err instanceof ApiError ? err : new ApiError(err?.message || 'Failed to fetch resources'));
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, selectedType, selectedDomain, selectedEcosystem]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadResources();
    }, 200);
    return () => clearTimeout(timer);
  }, [loadResources]);

  const handleReset = () => {
    setSearchQuery('');
    setSelectedType('');
    setSelectedDomain('');
    setSelectedEcosystem('');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar />

      <main className="container" style={{ flex: 1, padding: '2rem 1.5rem 4rem' }}>
        {/* Page Title & Mission */}
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Registry Explorer
            </span>
          </div>
          <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.025em' }}>
            Robotics Component Registry
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1.05rem', marginTop: '0.4rem', maxWidth: '800px' }}>
            Discover, inspect, and evaluate open-source robotics packages, drivers, algorithms, simulation models, and platform dependencies.
          </p>
        </div>

        {/* Search & Filter Bar */}
        <SearchAndFilters
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          selectedType={selectedType}
          onTypeChange={setSelectedType}
          selectedDomain={selectedDomain}
          onDomainChange={setSelectedDomain}
          selectedEcosystem={selectedEcosystem}
          onEcosystemChange={setSelectedEcosystem}
          totalResults={total}
          onReset={handleReset}
        />

        {/* API Error / Unavailable State */}
        {error && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '8px',
              padding: '1.5rem',
              marginBottom: '2rem',
            }}
            data-testid="api-error-state"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fca5a5' }}>
                {error.isNetworkError ? 'Backend API Service Unreachable' : 'Registry Query Error'}
              </h3>
            </div>
            <p style={{ color: '#e2e8f0', fontSize: '0.9rem', lineHeight: '1.5', marginBottom: '1rem' }}>
              {error.message}
            </p>
            {error.isNetworkError && (
              <div style={{ background: '#090d16', padding: '0.85rem 1rem', borderRadius: '6px', fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: '#93c5fd', marginBottom: '1rem' }}>
                <p style={{ color: 'var(--text-dim)', marginBottom: '0.25rem' }}># Start the local OpenRobo REST API server:</p>
                <code>pnpm dev:api</code> or <code>python -m uvicorn apps.api.main:app --port 8000</code>
              </div>
            )}
            <button
              onClick={loadResources}
              style={{
                background: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                color: '#fca5a5',
                borderRadius: '6px',
                padding: '0.4rem 1rem',
                fontSize: '0.85rem',
                fontWeight: 600,
              }}
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* Loading State */}
        {isLoading && !error && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.25rem' }} data-testid="loading-state">
            {[1, 2, 3, 4, 5, 6].map((idx) => (
              <div
                key={idx}
                style={{
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  padding: '1.25rem',
                  height: '210px',
                  opacity: 0.6,
                  animation: 'pulse 1.5s infinite',
                }}
              >
                <div style={{ height: '14px', width: '40%', background: 'var(--border-color)', borderRadius: '4px', marginBottom: '1rem' }}></div>
                <div style={{ height: '22px', width: '70%', background: 'var(--border-color)', borderRadius: '4px', marginBottom: '0.75rem' }}></div>
                <div style={{ height: '14px', width: '90%', background: 'var(--border-color)', borderRadius: '4px', marginBottom: '0.5rem' }}></div>
                <div style={{ height: '14px', width: '80%', background: 'var(--border-color)', borderRadius: '4px' }}></div>
              </div>
            ))}
          </div>
        )}

        {/* Zero Results State */}
        {!isLoading && !error && resources.length === 0 && (
          <div
            style={{
              background: 'var(--panel-bg)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '3rem 2rem',
              textAlign: 'center',
            }}
            data-testid="empty-state"
          >
            <div style={{ color: 'var(--text-dim)', marginBottom: '1rem' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ margin: '0 auto' }}>
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                <line x1="8" y1="11" x2="14" y2="11"></line>
              </svg>
            </div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
              No Robotics Resources Found
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', maxWidth: '480px', margin: '0 auto 1.5rem' }}>
              No manifests matched your search criteria. Try broadening your keyword or clearing active type/domain filters.
            </p>
            <button
              onClick={handleReset}
              style={{
                background: 'var(--accent-cyan-glow)',
                border: '1px solid var(--accent-cyan)',
                color: 'var(--accent-cyan)',
                borderRadius: '6px',
                padding: '0.5rem 1.25rem',
                fontSize: '0.9rem',
                fontWeight: 600,
              }}
            >
              Reset All Filters
            </button>
          </div>
        )}

        {/* Resource Grid */}
        {!isLoading && !error && resources.length > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
              gap: '1.25rem',
            }}
            data-testid="resource-grid"
          >
            {resources.map((res) => (
              <ResourceCard
                key={res.id}
                resource={res}
                onSelect={(r) => setSelectedResource(r)}
              />
            ))}
          </div>
        )}
      </main>

      {/* Detail Drawer */}
      <ResourceDetailDrawer
        resource={selectedResource}
        onClose={() => setSelectedResource(null)}
      />
    </div>
  );
}
