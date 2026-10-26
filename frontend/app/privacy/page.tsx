import type { Metadata } from "next";

import { LegalDoc } from "@/components/public/LegalDoc";
import { PublicPage } from "@/components/public/PublicPage";
import { LEGAL_UPDATED, PRIVACY } from "@/lib/legal-content";

export const metadata: Metadata = {
  title: "Privacy Policy — SAIA",
  description: "How SAIA collects and uses data: email, name and project data; crypto payments only; no selling of data.",
};

export default function PrivacyPage() {
  return (
    <PublicPage
      en={<LegalDoc copy={PRIVACY.en} updated={LEGAL_UPDATED.en} updatedLabel="Last updated" />}
      fa={<LegalDoc copy={PRIVACY.fa} updated={LEGAL_UPDATED.fa} updatedLabel="آخرین به‌روزرسانی" />}
    />
  );
}
