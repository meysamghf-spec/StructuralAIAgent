"use client";

import {
  ISSUE_STATUSES,
  approveFix,
  checkPlatformAdmin,
  featureRequestLine,
  isFeatureRequest,
  listPlatformIssues,
  postBackPlatformIssue,
  proposeFix,
  sortIssues,
  type PlatformIssue,
} from "@/lib/platform-issues";
import { useCallback, useEffect, useState } from "react";

export default function PlatformIssuesClient() {
  const [admin, setAdmin] = useState<boolean | null>(null);
  const [issues, setIssues] = useState<PlatformIssue[]>([]);
  const [openOnly, setOpenOnly] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("triaged");
  const [fixNote, setFixNote] = useState("");
  const [prUrl, setPrUrl] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [draftDiff, setDraftDiff] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setIssues(sortIssues(await listPlatformIssues(openOnly)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load issues");
    } finally {
      setBusy(false);
    }
  }, [openOnly]);

  useEffect(() => {
    void checkPlatformAdmin().then(setAdmin);
  }, []);
  useEffect(() => {
    if (admin) void refresh();
  }, [admin, refresh]);

  const selected = issues.find((item) => item.id === selectedId) ?? null;
  useEffect(() => {
    if (selected) {
      setStatus(selected.status);
      setFixNote(selected.fix_note ?? "");
      setPrUrl(selected.fix_pr_url ?? "");
    }
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(action: () => Promise<PlatformIssue>, done: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await action();
      setIssues((current) => sortIssues(current.map((item) => (item.id === updated.id ? updated : item))));
      setNotice(done);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  if (admin === null) return <p className="muted">Checking admin access…</p>;
  if (!admin) {
    return (
      <section className="panel-stack">
        <header className="page-header">
          <p className="eyebrow">Admin</p>
          <h2 className="page-dup-title">Platform issues</h2>
        </header>
        <div className="alert error" role="alert">
          Platform admin access is required. Ask the owner to add your account to <code>PLATFORM_ADMIN_ACCOUNTS</code>.
        </div>
      </section>
    );
  }

  return (
    <section className="panel-stack">
      <header className="page-header">
        <p className="eyebrow">Admin</p>
        <h2 className="page-dup-title">Platform issues</h2>
        <p className="muted">
          Problems the chat helper noticed or users reported. Fixes are drafts only: nothing is applied, merged or deployed from this page.
        </p>
      </header>
      {error ? <div className="alert error" role="alert">{error}</div> : null}
      {notice ? <div className="alert" role="status">{notice}</div> : null}
      <label>
        <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} /> Open only
      </label>
      <div className="issues-layout">
        <ul className="issues-list" aria-label="Issues">
          {issues.length === 0 ? <li className="muted">{busy ? "Loading…" : "No issues."}</li> : null}
          {issues.map((issue) => (
            <li key={issue.id}>
              <button
                type="button"
                className={issue.id === selectedId ? "issue-row active" : "issue-row"}
                onClick={() => setSelectedId(issue.id)}
              >
                <span className={`issue-sev issue-sev-${issue.severity}`}>{isFeatureRequest(issue) ? "feature" : issue.severity}</span>
                <strong dir="auto">{issue.title}</strong>
                <span className="muted">
                  {issue.status} · ×{issue.occurrences}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {selected ? (
          <article className="issue-detail panel">
            <h3 dir="auto">{selected.title}</h3>
            <p className="muted">
              {selected.category} · {selected.source} · page {selected.page || "—"} · {selected.created_at}
            </p>
            {isFeatureRequest(selected) ? (
              <p data-testid="feature-request-line"><strong>Feature request:</strong> {featureRequestLine(selected)}</p>
            ) : null}
            {selected.summary ? <p dir="auto">{selected.summary}</p> : null}
            {selected.user_message ? <pre dir="auto">{selected.user_message}</pre> : null}
            {selected.error_text ? <pre>{selected.error_text}</pre> : null}
            {selected.suspected_files?.length ? <p>Suspected files: {selected.suspected_files.join(", ")}</p> : null}

            <h4>Post back to the user</h4>
            <label>
              Status
              <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                {ISSUE_STATUSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>
            <label>
              Note shown in the user's chat
              <textarea className="input" rows={2} value={fixNote} maxLength={1000} onChange={(e) => setFixNote(e.target.value)} />
            </label>
            <label>
              Fix PR URL
              <input className="input" value={prUrl} onChange={(e) => setPrUrl(e.target.value)} />
            </label>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() =>
                void run(
                  () => postBackPlatformIssue(selected.id, { status, fix_note: fixNote, fix_pr_url: prUrl }),
                  "Status posted back.",
                )
              }
            >
              Post back
            </button>

            <h4>Proposed fix (draft)</h4>
            {selected.proposed_fix ? (
              <div className="issue-fix">
                <p>
                  <strong>{selected.proposed_fix.title}</strong> — {selected.proposed_fix.status ?? "draft"}
                  {selected.proposed_fix.approved_by ? ` (approved by ${selected.proposed_fix.approved_by})` : ""}
                </p>
                {selected.proposed_fix.body ? <pre>{selected.proposed_fix.body}</pre> : null}
                {selected.proposed_fix.diff ? <pre dir="ltr">{selected.proposed_fix.diff}</pre> : null}
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy || selected.proposed_fix.status === "approved"}
                  onClick={() => void run(() => approveFix(selected.id), "Fix marked approved. Merge and deploy remain manual in GitHub.")}
                >
                  Approve fix (does not merge or deploy)
                </button>
              </div>
            ) : (
              <div className="issue-fix">
                <input className="input" placeholder="Title" value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} />
                <textarea className="input" rows={3} placeholder="PR description" value={draftBody} onChange={(e) => setDraftBody(e.target.value)} />
                <textarea className="input" rows={5} placeholder="Unified diff (optional)" value={draftDiff} onChange={(e) => setDraftDiff(e.target.value)} />
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy || !draftTitle.trim()}
                  onClick={() =>
                    void run(
                      () =>
                        proposeFix(selected.id, {
                          kind: draftDiff.trim() ? "diff" : "pr_draft",
                          title: draftTitle.trim(),
                          body: draftBody,
                          diff: draftDiff,
                        }),
                      "Fix draft saved (not applied).",
                    )
                  }
                >
                  Save fix draft
                </button>
              </div>
            )}
          </article>
        ) : (
          <p className="muted">Select an issue.</p>
        )}
      </div>
    </section>
  );
}
