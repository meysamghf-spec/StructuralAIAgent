export default function WorkspacePlaceholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Workspace</p>
        <h2>{title}</h2>
        <p className="subtitle">{description}</p>
      </header>
      <section className="card">
        <p className="muted">
          This area is wired into the backend architecture. Use project pages and API endpoints
          for full workflows while the dedicated UI expands.
        </p>
      </section>
    </section>
  );
}
