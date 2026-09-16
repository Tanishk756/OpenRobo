'use client';

import React from 'react';
import Link from 'next/link';
import Navbar from '../components/Navbar';

export default function HomePage() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar />

      <main className="container" style={{ flex: 1, padding: '3rem 1.5rem 5rem' }}>
        {/* Hero Section */}
        <section style={{ marginBottom: '3.5rem', textAlign: 'center', maxWidth: '850px', margin: '0 auto 3.5rem' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.25rem 0.75rem', borderRadius: '9999px', background: 'var(--accent-cyan-glow)', border: '1px solid rgba(6, 182, 212, 0.3)', marginBottom: '1.25rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
              MILESTONE 1 — REGISTRY ENGINE & RESOURCE DISCOVERY
            </span>
          </div>

          <h1 style={{ fontSize: '3rem', fontWeight: 900, color: 'var(--text-main)', letterSpacing: '-0.035em', lineHeight: '1.15', marginBottom: '1.25rem' }}>
            Global Open Robotics Commons Platform
          </h1>

          <p style={{ color: 'var(--text-muted)', fontSize: '1.2rem', lineHeight: '1.6', marginBottom: '2rem' }}>
            Discover, compose, validate, simulate, and deploy robotics software and hardware stacks with verified multi-dimensional compatibility reasoning.
          </p>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <Link
              href="/resources"
              style={{
                background: 'var(--accent-cyan)',
                color: '#090d16',
                fontWeight: 700,
                fontSize: '1rem',
                padding: '0.75rem 1.75rem',
                borderRadius: '6px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                boxShadow: '0 4px 14px rgba(6, 182, 212, 0.4)',
                transition: 'all 0.15s ease',
              }}
              data-testid="explore-registry-btn"
            >
              <span>Explore Resource Registry</span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </Link>

            <a
              href="https://github.com/Tanishk756/OpenRobo"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                background: 'var(--panel-bg)',
                color: 'var(--text-main)',
                fontWeight: 600,
                fontSize: '1rem',
                padding: '0.75rem 1.5rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span>View Source Code</span>
            </a>
          </div>
        </section>

        {/* Feature Grid */}
        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginBottom: '3.5rem' }}>
          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.5rem' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '6px', background: 'rgba(6, 182, 212, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem', color: 'var(--accent-cyan)' }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                <polyline points="2 17 12 22 22 17"></polyline>
                <polyline points="2 12 12 17 22 12"></polyline>
              </svg>
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
              Canonical Metadata Schema
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
              JSON Schema Draft 2020-12 specifications for packages, hardware, models, and complete robotics stacks.
            </p>
          </div>

          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.5rem' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '6px', background: 'rgba(59, 130, 246, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem', color: 'var(--accent-blue)' }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
              Robotics Knowledge Graph
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
              Relational graph nodes and edges supporting 17+ relationship predicates for cross-domain dependency reasoning.
            </p>
          </div>

          <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.5rem' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem', color: 'var(--accent-emerald)' }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                <line x1="8" y1="21" x2="16" y2="21"></line>
                <line x1="12" y1="17" x2="12" y2="21"></line>
              </svg>
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
              Local-First Offline CLI
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
              Lightweight Typer CLI for local manifest validation, offline inspection, and workspace scaffolding.
            </p>
          </div>
        </section>

        {/* Technical Specification Matrix */}
        <section style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.75rem' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '1rem' }}>
            Architecture Status
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
            <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <h4 style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>License</h4>
              <p style={{ fontWeight: 600, marginTop: '0.25rem', color: 'var(--text-main)' }}>Apache-2.0 (Strict)</p>
            </div>
            <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <h4 style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>REST API</h4>
              <p style={{ fontWeight: 600, marginTop: '0.25rem', color: 'var(--text-main)' }}>FastAPI + Async SQLAlchemy</p>
            </div>
            <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <h4 style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Web Frontend</h4>
              <p style={{ fontWeight: 600, marginTop: '0.25rem', color: 'var(--text-main)' }}>Next.js 14 App Router</p>
            </div>
            <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <h4 style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Test DB Strategy</h4>
              <p style={{ fontWeight: 600, marginTop: '0.25rem', color: 'var(--text-main)' }}>SQLite in-memory isolation</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
