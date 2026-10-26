import type { Metadata } from "next";

import { LegalDoc } from "@/components/public/LegalDoc";
import { PublicPage } from "@/components/public/PublicPage";
import { LEGAL_UPDATED, TERMS } from "@/lib/legal-content";

export const metadata: Metadata = {
  title: "Terms of Service — SAIA",
  description: "Terms of service for SAIA, the chat-first structural engineering assistant.",
};

export default function TermsPage() {
  return (
    <PublicPage
      en={<LegalDoc copy={TERMS.en} updated={LEGAL_UPDATED.en} updatedLabel="Last updated" />}
      fa={<LegalDoc copy={TERMS.fa} updated={LEGAL_UPDATED.fa} updatedLabel="آخرین به‌روزرسانی" />}
    />
  );
}
