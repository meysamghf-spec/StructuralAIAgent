"use client";

import { useEffect, useState } from "react";
import { pageCount, pageSlice, TABLE_PAGE_SIZE } from "@/lib/paging";

/** Rows of the current page + reset to page 1 when the row set changes. Small tables (≤ one page) are unchanged. */
export function usePaged<T>(rows: readonly T[], size = TABLE_PAGE_SIZE) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [rows.length]);
  const pages = pageCount(rows.length, size);
  return { page: Math.min(page, pages - 1), pages, setPage, rows: pageSlice(rows, page, size), total: rows.length, size };
}

type Props = { page: number; pages: number; total: number; size: number; setPage: (p: number) => void; lang?: "en" | "fa" };

export function TablePager({ page, pages, total, size, setPage, lang = "en" }: Props) {
  if (pages <= 1) return null;
  const fa = lang === "fa";
  const from = page * size + 1, to = Math.min(total, (page + 1) * size);
  return (
    <div className="table-pager" data-testid="table-pager" style={{ display: "flex", gap: 8, alignItems: "center", margin: "6px 0", fontSize: 13 }}>
      <button type="button" disabled={page <= 0} onClick={() => setPage(page - 1)}>{fa ? "قبلی" : "Previous"}</button>
      <span dir="ltr">{from}–{to} / {total}</span>
      <button type="button" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>{fa ? "بعدی" : "Next"}</button>
    </div>
  );
}
