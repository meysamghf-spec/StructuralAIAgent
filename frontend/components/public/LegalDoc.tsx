import type { PageCopy } from "@/lib/legal-content";

export function LegalDoc({ copy, updated, updatedLabel }: { copy: PageCopy; updated: string; updatedLabel: string }) {
  return (
    <>
      <h1>{copy.title}</h1>
      <p className="muted">{updatedLabel}: {updated}</p>
      <p>{copy.intro}</p>
      {copy.sections.map((s) => (
        <section key={s.h}>
          <h2>{s.h}</h2>
          {s.p?.map((t) => <p key={t}>{t}</p>)}
          {s.ul ? <ul>{s.ul.map((t) => <li key={t}>{t}</li>)}</ul> : null}
        </section>
      ))}
    </>
  );
}
