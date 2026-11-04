import { describe, expect, it } from "vitest";
import { pageCount, pageSlice } from "@/lib/paging";

describe("table paging", () => {
  it("splits big tables and clamps pages", () => {
    const rows = Array.from({ length: 450 }, (_, i) => i);
    expect(pageCount(rows.length, 200)).toBe(3);
    expect(pageSlice(rows, 2, 200)).toEqual(rows.slice(400));
    expect(pageSlice(rows, 9, 200)).toEqual(rows.slice(400));
    expect(pageCount(0, 200)).toBe(1);
    expect(pageSlice([1, 2], 0, 200)).toEqual([1, 2]);
  });
});
