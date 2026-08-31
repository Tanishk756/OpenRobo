export default function HomePage() {
  return (
    <div style={{ padding: '3rem 2rem', maxWidth: '1100px', margin: '0 auto' }}>
      <header style={{ marginBottom: '2.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.025em' }}>
          OpenRobo
        </h1>
        <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem', fontSize: '1.1rem' }}>
          Global Open Robotics Commons Platform
        </p>
      </header>

      <section style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.5rem', marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.25rem', color: 'var(--accent-cyan)', marginBottom: '0.75rem' }}>
          Platform Foundation Status (Milestone 0)
        </h2>
        <p style={{ color: 'var(--text-main)', marginBottom: '1rem' }}>
          OpenRobo architecture foundation is initialized. Real metadata indexers, knowledge graph query APIs, schema validators, and CLI utilities are connected.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
          <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
            <h3 style={{ fontSize: '0.95rem', color: 'var(--text-muted)' }}>Core License</h3>
            <p style={{ fontWeight: 600, marginTop: '0.25rem' }}>Apache-2.0</p>
          </div>
          <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
            <h3 style={{ fontSize: '0.95rem', color: 'var(--text-muted)' }}>API Status</h3>
            <p style={{ fontWeight: 600, marginTop: '0.25rem' }}>/api/v1/health</p>
          </div>
          <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
            <h3 style={{ fontSize: '0.95rem', color: 'var(--text-muted)' }}>Schema Engine</h3>
            <p style={{ fontWeight: 600, marginTop: '0.25rem' }}>Draft 2020-12 Validated</p>
          </div>
        </div>
      </section>
    </div>
  );
}
