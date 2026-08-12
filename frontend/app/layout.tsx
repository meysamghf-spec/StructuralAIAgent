import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Engineering AI Platform",
  description: "AI-powered engineering platform — Phase 1 Milestone 1",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
