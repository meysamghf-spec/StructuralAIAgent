"use client";

import { useUiLang } from "@/hooks/useUiLang";

/** SAIA logomark: a truss/portal frame whose joints are AI network nodes. Pure SVG, no external assets. */
export function SaiaMark({ size = 36, title }: { size?: number; title?: string }) {
  return (
    <svg
      className="saia-mark"
      width={size}
      height={size}
      viewBox="0 0 40 40"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <defs>
        <linearGradient id="saia-g" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="0.55" stopColor="#0ea5e9" />
          <stop offset="1" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="10" fill="url(#saia-g)" />
      <g stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none">
        <path d="M11 32V17.5M29 32V17.5M8 32h24" />
        <path d="M11 17.5 20 9l9 8.5H11Z" strokeWidth="1.8" opacity=".9" />
        <path d="M11 32 29 17.5M29 32 11 17.5" strokeWidth="1.2" opacity=".45" />
      </g>
      <g fill="#fff">
        <circle cx="20" cy="9" r="3.1" />
        <circle cx="11" cy="17.5" r="2.4" />
        <circle cx="29" cy="17.5" r="2.4" />
      </g>
      <circle cx="20" cy="9" r="1.3" fill="#0ea5e9" />
    </svg>
  );
}

type Size = "sm" | "md" | "lg";

/** Logomark + SAIA wordmark (+ optional tagline). `dir="ltr"` keeps the Latin wordmark stable in RTL pages. */
export function SaiaLogo({ size = "md", tagline = true, className = "" }: { size?: Size; tagline?: boolean; className?: string }) {
  const { t } = useUiLang();
  const px = size === "lg" ? 52 : size === "md" ? 40 : 30;
  return (
    <span className={`saia-logo saia-logo--${size} ${className}`.trim()} dir="ltr" aria-label="SAIA">
      <SaiaMark size={px} />
      <span className="saia-logo-text">
        <span className="saia-wordmark">SAIA</span>
        {tagline ? <span className="saia-tagline" dir="auto">{t("Chat with your structural AI")}</span> : null}
      </span>
    </span>
  );
}
