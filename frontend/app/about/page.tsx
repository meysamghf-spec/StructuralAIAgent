import type { Metadata } from "next";
import Link from "next/link";

import { PublicPage } from "@/components/public/PublicPage";
import { ABOUT } from "@/lib/legal-content";

export const metadata: Metadata = {
  title: "SAIA — Chat with your structural AI",
  description: "SAIA: chat-first, AI-driven structural engineering — analysis, design, validation, approval and memory.",
};

function Landing({ c }: { c: (typeof ABOUT)["en"] | (typeof ABOUT)["fa"] }) {
  return (
    <>
      <h1>{c.title}</h1>
      <p className="public-lead">{c.intro}</p>
      <ul className="public-features">
        {c.features.map(([h, d]) => (
          <li key={h}><strong>{h}</strong><span>{d}</span></li>
        ))}
      </ul>
      <p className="public-cta">
        <Link className="button" href="/login">{c.signIn}</Link>
        <Link className="button secondary" href="/register">{c.create}</Link>
      </p>
    </>
  );
}

export default function AboutPage() {
  return <PublicPage en={<Landing c={ABOUT.en} />} fa={<Landing c={ABOUT.fa} />} />;
}
