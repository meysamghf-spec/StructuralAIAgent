import { AppShell } from "@/components/AppShell";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StructuralAIAgent — Engineering Workspace",
  description: "Structural engineering AI platform workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
