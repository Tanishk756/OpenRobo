'use client';

import React, { useEffect, useState } from 'react';
import { downloadWorkspaceZip, previewWorkspace } from '../../lib/api/client';
import { WorkspacePreviewResponse } from '../../lib/api/types';

interface WorkspaceModalProps {
  isOpen: boolean;
  onClose: () => void;
  manifest: Record<string, unknown>;
  stackName: string;
}

export function WorkspaceModal({ isOpen, onClose, manifest, stackName }: WorkspaceModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<WorkspacePreviewResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>('README.md');
  const [downloading, setDownloading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    let isMounted = true;
    setLoading(true);
    setError(null);

    previewWorkspace({ manifest, allow_incompatible: true })
      .then((data) => {
        if (!isMounted) return;
        setPreview(data);
        const fileKeys = Object.keys(data.files || {});
        if (fileKeys.includes('README.md')) {
          setSelectedFile('README.md');
        } else if (fileKeys.length > 0) {
          setSelectedFile(fileKeys[0]);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err?.message || 'Failed to synthesize workspace preview.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, manifest]);

  if (!isOpen) return null;

  const handleDownload = async () => {
    try {
      setDownloading(true);
      const blob = await downloadWorkspaceZip({ manifest, allow_incompatible: true });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${preview?.workspace_name || stackName || 'openrobo_ws'}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(`Download failed: ${err.message || 'Unknown error'}`);
    } finally {
      setDownloading(false);
    }
  };

  const handleCopy = () => {
    if (!preview?.files[selectedFile]) return;
    navigator.clipboard.writeText(preview.files[selectedFile]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filesList = preview ? Object.keys(preview.files).sort() : [];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '24px',
      }}
    >
      <div
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '14px',
          width: '100%',
          maxWidth: '1100px',
          height: '85vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
        }}
      >
        {/* MODAL HEADER */}
        <div
          style={{
            padding: '16px 24px',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--bg-card)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, var(--accent-cyan), #3b82f6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1rem',
                fontWeight: 800,
                color: '#000',
              }}
            >
              WS
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Workspace & Deployment Generator
                </span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: '999px',
                    background: 'rgba(56,189,248,0.15)',
                    color: 'var(--accent-cyan)',
                    border: '1px solid rgba(56,189,248,0.3)',
                    fontWeight: 600,
                  }}
                >
                  v{preview?.generator_version || '0.5.0'}
                </span>
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Targeting <strong style={{ color: 'var(--text-primary)' }}>{preview?.target_distro || 'humble'}</strong> on {preview?.target_os || 'ubuntu-22.04'} ({preview?.target_arch || 'x86_64'})
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {preview && (
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontWeight: 600,
                  background:
                    preview.compatibility_verdict === 'COMPATIBLE'
                      ? 'rgba(34,197,94,0.15)'
                      : 'rgba(234,179,8,0.15)',
                  color:
                    preview.compatibility_verdict === 'COMPATIBLE' ? '#4ade80' : '#facc15',
                  border: `1px solid ${preview.compatibility_verdict === 'COMPATIBLE' ? 'rgba(34,197,94,0.3)' : 'rgba(234,179,8,0.3)'}`,
                }}
              >
                {preview.compatibility_verdict}
              </span>
            )}
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '1.3rem',
                padding: '4px',
              }}
            >
              &times;
            </button>
          </div>
        </div>

        {/* MODAL BODY */}
        {loading ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
            }}
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                border: '3px solid rgba(56,189,248,0.2)',
                borderTopColor: 'var(--accent-cyan)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Synthesizing deterministic colcon workspace & container artifacts...
            </div>
          </div>
        ) : error ? (
          <div style={{ padding: '32px', textAlign: 'center' }}>
            <div style={{ color: '#f87171', fontWeight: 600, marginBottom: '8px' }}>
              Generation Failed
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{error}</div>
          </div>
        ) : preview ? (
          <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
            {/* LEFT SIDEBAR: FILE LIST & DIAGNOSTICS */}
            <div
              style={{
                width: '340px',
                borderRight: '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                background: 'rgba(0,0,0,0.2)',
              }}
            >
              {/* SUMMARY STATS */}
              <div
                style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border-color)',
                  display: 'flex',
                  gap: '8px',
                  flexWrap: 'wrap',
                }}
              >
                <div
                  style={{
                    flex: 1,
                    minWidth: '90px',
                    padding: '8px 10px',
                    background: 'var(--bg-card)',
                    borderRadius: '6px',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Files</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {preview.file_count}
                  </div>
                </div>
                <div
                  style={{
                    flex: 1,
                    minWidth: '90px',
                    padding: '8px 10px',
                    background: 'var(--bg-card)',
                    borderRadius: '6px',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Total Size</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {(preview.total_bytes / 1024).toFixed(1)} KB
                  </div>
                </div>
              </div>

              {/* WARNINGS PANEL */}
              {preview.warnings && preview.warnings.length > 0 && (
                <div
                  style={{
                    margin: '10px 12px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'rgba(234,179,8,0.1)',
                    border: '1px solid rgba(234,179,8,0.25)',
                    fontSize: '0.75rem',
                    color: '#facc15',
                  }}
                >
                  <div style={{ fontWeight: 700, marginBottom: '4px' }}>⚠️ Generation Notes:</div>
                  <ul style={{ paddingLeft: '14px', margin: 0 }}>
                    {preview.warnings.map((w, idx) => (
                      <li key={idx} style={{ marginTop: '2px' }}>
                        {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* FILE TREE SELECTOR */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '10px 8px' }}>
                <div
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: 'var(--text-muted)',
                    padding: '4px 8px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}
                >
                  Generated File Hierarchy
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '4px' }}>
                  {filesList.map((fpath) => {
                    const isSelected = selectedFile === fpath;
                    const fileName = fpath.split('/').pop() || fpath;
                    const dirPath = fpath.includes('/') ? fpath.substring(0, fpath.lastIndexOf('/')) : '';

                    return (
                      <button
                        key={fpath}
                        onClick={() => setSelectedFile(fpath)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          border: isSelected
                            ? '1px solid var(--accent-cyan)'
                            : '1px solid transparent',
                          background: isSelected ? 'rgba(56,189,248,0.12)' : 'transparent',
                          color: isSelected ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          fontSize: '0.8rem',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <span style={{ color: isSelected ? 'var(--text-primary)' : 'var(--text-muted)', marginRight: '6px' }}>
                            {dirPath ? `${dirPath}/` : ''}
                          </span>
                          <strong style={{ color: isSelected ? 'var(--accent-cyan)' : 'var(--text-primary)' }}>
                            {fileName}
                          </strong>
                        </div>
                        <span
                          style={{
                            fontSize: '0.7rem',
                            color: 'var(--text-muted)',
                            marginLeft: '8px',
                          }}
                        >
                          {preview.files[fpath].length}B
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* RIGHT PANE: FILE CONTENT VIEWER */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div
                style={{
                  padding: '10px 16px',
                  borderBottom: '1px solid var(--border-color)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'rgba(0,0,0,0.1)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <code style={{ fontSize: '0.85rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                    {selectedFile}
                  </code>
                  {selectedFile.endsWith('.sh') && (
                    <span
                      style={{
                        fontSize: '0.65rem',
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: 'rgba(34,197,94,0.15)',
                        color: '#4ade80',
                      }}
                    >
                      executable
                    </span>
                  )}
                </div>

                <button
                  onClick={handleCopy}
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    color: copied ? '#4ade80' : 'var(--text-secondary)',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {copied ? '✓ Copied' : 'Copy File Content'}
                </button>
              </div>

              <div
                style={{
                  flex: 1,
                  overflow: 'auto',
                  padding: '16px',
                  background: 'var(--bg-primary)',
                  fontFamily: 'monospace',
                  fontSize: '0.82rem',
                  lineHeight: 1.5,
                  color: 'var(--text-primary)',
                  whiteSpace: 'pre',
                }}
              >
                {preview.files[selectedFile] || '// No content'}
              </div>
            </div>
          </div>
        ) : null}

        {/* MODAL FOOTER */}
        <div
          style={{
            padding: '14px 24px',
            borderTop: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--bg-card)',
          }}
        >
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Deterministic colcon build tree & multi-stage container deployment.
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                padding: '8px 16px',
                borderRadius: '6px',
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}
            >
              Close
            </button>
            <button
              onClick={handleDownload}
              disabled={downloading || !preview}
              style={{
                background: 'linear-gradient(135deg, var(--accent-cyan), #3b82f6)',
                color: '#000',
                border: 'none',
                padding: '8px 20px',
                borderRadius: '6px',
                fontSize: '0.85rem',
                fontWeight: 700,
                cursor: downloading || !preview ? 'not-allowed' : 'pointer',
                opacity: downloading || !preview ? 0.6 : 1,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              {downloading ? 'Packaging ZIP...' : '⚡ Download colcon Workspace (.zip)'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}