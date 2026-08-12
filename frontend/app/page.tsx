export default function HomePage() {
  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">Phase 1 — Milestone 1</p>
        <h1>Engineering AI Platform</h1>
        <p className="subtitle">
          Structural Engineering is the initial domain. The platform core remains
          domain-independent and extensible for future engineering disciplines.
        </p>
        <div className="status-card">
          <h2>Repository Bootstrap</h2>
          <ul>
            <li>Backend: FastAPI health endpoint</li>
            <li>Frontend: Next.js + React + TypeScript</li>
            <li>Database: PostgreSQL migration infrastructure</li>
            <li>Architecture boundaries prepared — no integrations yet</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
