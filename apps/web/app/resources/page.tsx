'use client';

import React, { useState, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Navbar from '../../components/Navbar';
import SearchAndFilters from '../../components/SearchAndFilters';
import ResourceCard from '../../components/ResourceCard';
import ResourceDetailDrawer from '../../components/ResourceDetailDrawer';
import { Resource, SearchResultHit, SearchFacetDistribution } from '../../lib/api/types';
import { searchResources, fetchSearchFacets, ApiError } from '../../lib/api/client';

function ResourcesExplorerContent() {
  const searchParams = useSearchParams();

  // Read initial filter values from URL search params
  const [searchQuery, setSearchQuery] = useState(searchParams?.get('q') || '');
  const [selectedType, setSelectedType] = useState(searchParams?.get('type') || '');
  const [selectedDomain, setSelectedDomain] = useState(searchParams?.get('domain') || '');
  const [selectedEcosystem, setSelectedEcosystem] = useState(searchParams?.get('ecosystem') || '');

  const [hits, setHits] = useState<SearchResultHit[]>([]);
  const [facets, setFacets] = useState<SearchFacetDistribution | null>(null);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);

  // Sync state changes to browser URL query string without reloading page
  const updateUrlParams = useCallback((q: string, type: string, domain: string, eco: string) => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams();
    if (q.trim()) params.set('q', q.trim());
    if (type) params.set('type', type);
    if (domain) params.set('domain', domain);
    if (eco) params.set('ecosystem', eco);

    const queryStr = params.toString();
    const targetUrl = queryStr ? `/resources?${queryStr}` : '/resources';
    window.history.replaceState(null, '', targetUrl);
  }, []);

  const loadResources = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const searchRes = await searchResources({
        q: searchQuery.trim() || undefined,
        type: selectedType || undefined,
        domain: selectedDomain || undefined,
        ecosystem: selectedEcosystem || undefined,
        limit: 50,
        offset: 0,
      });

      setHits(searchRes.items);
      setTotal(searchRes.total);
      if (searchRes.facets) {
        setFacets(searchRes.facets);
      } else {
        const facetRes = await fetchSearchFacets(searchQuery.trim() || undefined);
        setFacets(facetRes);
      }
    } catch (err) {
      setError(err as ApiError);
      setHits([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, selectedType, selectedDomain, selectedEcosystem]);

  useEffect(() => {
    updateUrlParams(searchQuery, selectedType, selectedDomain, selectedEcosystem);
    const timer = setTimeout(() => {
      loadResources();
    }, 200);
    return () => clearTimeout(timer);
  }, [searchQuery, selectedType, selectedDomain, selectedEcosystem, loadResources, updateUrlParams]);

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
              Registry Explorer & Search
            </span>
          </div>
          <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.025em' }}>
            Robotics Component Registry
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1.05rem', marginTop: '0.4rem', maxWidth: '800px' }}>
            Discover, inspect, and evaluate open-source robotics packages, drivers, algorithms, simulation models, and platform dependencies with PostgreSQL-backed full-text and fuzzy search.
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
          facets={facets}
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
                {error.isNetworkError ? 'Backend API Service Unreachable' : 'Search Query Error'}
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
                cursor: 'pointer',
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
        {!isLoading && !error && hits.length === 0 && (
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
              No manifests matched your search criteria. Try broadening your query or clearing active filters.
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
                cursor: 'pointer',
              }}
            >
              Reset All Filters
            </button>
          </div>
        )}

        {/* Resource Grid with Ranked Hits */}
        {!isLoading && !error && hits.length > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
              gap: '1.25rem',
            }}
            data-testid="resource-grid"
          >
            {hits.map((hit) => (
              <ResourceCard
                key={hit.resource.id}
                resource={hit.resource}
                score={hit.score}
                highlights={hit.highlights}
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

export default function ResourcesPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: 'var(--bg-color)' }} />}>
      <ResourcesExplorerContent />
    </Suspense>
  );
}
