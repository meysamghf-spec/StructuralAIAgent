/** Client-side paging for big result tables (ETABS-scale models have tens of thousands of member rows). */
export const TABLE_PAGE_SIZE = 200;

export function pageCount(total: number, size = TABLE_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / size));
}

export function pageSlice<T>(rows: readonly T[], page: number, size = TABLE_PAGE_SIZE): T[] {
  const p = Math.min(Math.max(0, page), pageCount(rows.length, size) - 1);
  return rows.slice(p * size, (p + 1) * size);
}
