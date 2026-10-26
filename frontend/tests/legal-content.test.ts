import { describe, expect, it } from "vitest";
import { ABOUT, CONTACT_EMAIL, PRIVACY, PUBLIC_PATHS, TERMS } from "../lib/legal-content";

describe("public legal pages", () => {
  it("have matching EN/FA structure and the contact address", () => {
    for (const doc of [PRIVACY, TERMS]) {
      expect(doc.en.sections.length).toBe(doc.fa.sections.length);
      expect(JSON.stringify(doc.en)).toContain(CONTACT_EMAIL);
      expect(JSON.stringify(doc.fa)).toContain(CONTACT_EMAIL);
    }
    expect(ABOUT.en.features.length).toBe(ABOUT.fa.features.length);
  });
  it("state the key privacy facts", () => {
    const en = JSON.stringify(PRIVACY.en);
    expect(en).toMatch(/do not sell your data/);
    expect(en).toMatch(/cryptocurrency only/);
    expect(en).toMatch(/openid, email and profile/);
    expect(JSON.stringify(PRIVACY.fa)).toMatch(/رمزارز/);
  });
  it("lists Validation, Approval and Memory on the landing", () => {
    const names = ABOUT.en.features.map((f) => f[0]);
    expect(names).toEqual(expect.arrayContaining(["Validation", "Approval", "Memory"]));
  });
  it("exposes exactly the public paths", () => {
    expect([...PUBLIC_PATHS]).toEqual(["/about", "/privacy", "/terms"]);
  });
});
