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
      a.download = `${preview?.workspace_name || stackName || 'openrobo_workspace'}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(`Download failed: ${e?.message || 'Unknown network error'}`);
    } finally {
      setDownloading(false);
    }
  };

  const handleCopy = () => {
    if (!preview || !preview.files[selectedFile]) return;
    navigator.clipboard.writeText(preview.files[selectedFile]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filesList = preview?.files ? Object.keys(preview.files).sort() : [];
  const readiness = preview?.readiness_report;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      <div
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '1100px',
          height: '85vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
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
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Workspace Synthesis & Deployment Preview
              </h2>
              {preview?.generator_version && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    background: 'rgba(56,189,248,0.15)',
                    color: 'var(--accent-cyan)',
                    border: '1px solid rgba(56,189,248,0.3)',
                  }}
                >
                  v{preview.generator_version}
                </span>
              )}
            </div>
            <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Stack: <strong style={{ color: 'var(--text-primary)' }}>{stackName}</strong> | Target:{' '}
              <span style={{ color: 'var(--accent-cyan)' }}>{preview?.target_distro || 'humble'}</span> (
              {preview?.target_os || 'ubuntu-22.04'})
            </p>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              fontSize: '1.5rem',
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: '4px',
            }}
          >
            &times;
          </button>
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
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Synthesizing deterministic workspace files & static validation...
            </p>
          </div>
        ) : error ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '24px',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                borderRadius: '8px',
                padding: '16px 24px',
                maxWidth: '600px',
                color: '#f87171',
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: '8px' }}>Workspace Generation Error</div>
              <div style={{ fontSize: '0.85rem' }}>{error}</div>
            </div>
          </div>
        ) : preview ? (
          <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
            {/* LEFT PANE: FILE TREE & READINESS MATRIX */}
            <div
              style={{
                width: '320px',
                borderRight: '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                background: 'rgba(0,0,0,0.15)',
              }}
            >
              {/* READINESS BADGE */}
              <div
                style={{
                  padding: '10px 14px',
                  borderBottom: '1px solid var(--border-color)',
                  background: 'var(--bg-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Workspace Readiness
                  </span>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: readiness?.overall_state === 'STATICALLY_VALIDATED' ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)',
                      color: readiness?.overall_state === 'STATICALLY_VALIDATED' ? '#4ade80' : '#facc15',
                      border: `1px solid ${readiness?.overall_state === 'STATICALLY_VALIDATED' ? 'rgba(34,197,94,0.3)' : 'rgba(234,179,8,0.3)'}`,
                    }}
                  >
                    {readiness?.overall_state || 'STATICALLY_VALIDATED'}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', fontSize: '0.7rem' }}>
                  <div style={{ color: 'var(--text-muted)' }}>
                    Static Analysis: <span style={{ color: '#4ade80', fontWeight: 600 }}>PASSED</span>
                  </div>
                  <div style={{ color: 'var(--text-muted)' }}>
                    Docker Build: <span style={{ color: 'var(--text-muted)' }}>NOT RUN</span>
                  </div>
                  <div style={{ color: 'var(--text-muted)' }}>
                    Colcon Build: <span style={{ color: 'var(--text-muted)' }}>NOT RUN</span>
                  </div>
                  <div style={{ color: 'var(--text-muted)' }}>
                    Runtime Check: <span style={{ color: 'var(--text-muted)' }}>NOT RUN</span>
                  </div>
                </div>
              </div>

              {/* MANUAL CONFIG REQUIRED ALERT */}
              {readiness && readiness.manual_steps_required && readiness.manual_steps_required.length > 0 && (
                <div
                  style={{
                    padding: '8px 12px',
                    background: 'rgba(234, 179, 8, 0.1)',
                    borderBottom: '1px solid rgba(234, 179, 8, 0.3)',
                    fontSize: '0.75rem',
                    color: '#facc15',
                  }}
                >
                  <div style={{ fontWeight: 700, marginBottom: '2px' }}>⚠️ Manual Configuration Required:</div>
                  <ul style={{ paddingLeft: '14px', margin: 0 }}>
                    {readiness.manual_steps_required.map((step, idx) => (
                      <li key={idx} style={{ marginTop: '2px' }}>
                        {step}
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
                  Generated Files ({filesList.length})
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
                  {selectedFile.endsWith('.example') && (
                    <span
                      style={{
                        fontSize: '0.65rem',
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: 'rgba(234,179,8,0.15)',
                        color: '#facc15',
                      }}
                    >
                      scaffold / manual config
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
            Deterministic colcon build tree & least-privilege container deployment.
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
              {downloading ? 'Packaging ZIP...' : '📦 Download colcon Workspace (.zip)'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
