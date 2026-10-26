"""PostgreSQL IssueStore for the platform helper (table platform_issues)."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import get_connection
from app.platform_helper.issues import OPEN_STATUSES, IssueReport

_COLS = ("id", "title", "summary", "category", "severity", "source", "status", "page", "conversation_id", "project_id",
         "account_id", "user_message", "assistant_excerpt", "error_text", "steps_to_reproduce", "expected", "actual",
         "suspected_files", "app_version", "locale", "dedupe_key", "occurrences", "fix_note", "fix_pr_url",
         "proposed_fix", "created_at", "updated_at")
_JSON = {"steps_to_reproduce", "suspected_files", "proposed_fix"}
_UPDATABLE = set(_COLS) - {"id", "created_at"}


def _row_to_issue(row: dict[str, Any]) -> IssueReport:
    return IssueReport(**{c: row[c] for c in _COLS})


class PostgresPlatformIssueRepository:
    def add(self, issue: IssueReport) -> IssueReport:
        vals = [Jsonb(getattr(issue, c)) if c in _JSON else getattr(issue, c) for c in _COLS]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO platform_issues ({', '.join(_COLS)}) VALUES ({', '.join(['%s'] * len(_COLS))})", vals)
            conn.commit()
        return issue

    def get(self, issue_id: str) -> IssueReport | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM platform_issues WHERE id = %s", (issue_id,))
                row = cur.fetchone()
        return _row_to_issue(row) if row else None

    def list(self, *, statuses: tuple[str, ...] | None = None, account_id: str | None = None, limit: int = 100) -> list[IssueReport]:
        where, params = [], []
        if statuses:
            where.append("status = ANY(%s)")
            params.append(list(statuses))
        if account_id:
            where.append("account_id = %s")
            params.append(account_id)
        sql = "SELECT * FROM platform_issues" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at DESC LIMIT %s"
        params.append(max(1, min(limit, 500)))
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [_row_to_issue(r) for r in rows]

    def update(self, issue_id: str, **fields: Any) -> IssueReport | None:
        sets, params = [], []
        for k, v in fields.items():
            if k in _UPDATABLE:
                sets.append(f"{k} = %s")
                params.append(Jsonb(v) if k in _JSON else v)
        sets.append("updated_at = now()")
        params.append(issue_id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE platform_issues SET {', '.join(sets)} WHERE id = %s RETURNING *", params)
                row = cur.fetchone()
            conn.commit()
        return _row_to_issue(row) if row else None

    def find_open_by_dedupe(self, dedupe_key: str) -> IssueReport | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM platform_issues WHERE dedupe_key = %s AND status = ANY(%s) ORDER BY created_at DESC LIMIT 1",
                            (dedupe_key, list(OPEN_STATUSES)))
                row = cur.fetchone()
        return _row_to_issue(row) if row else None

    def delete(self, issue_id: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM platform_issues WHERE id = %s", (issue_id,))
                n = cur.rowcount
            conn.commit()
        return n > 0
