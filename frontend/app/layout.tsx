import { AppProviders } from "@/components/AppProviders";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SAIA — AI for structural engineering",
  description: "SAIA: AI for structural engineering — chat-first analysis, design and CAD workspace",
  icons: { icon: "/icon.svg" },
  themeColor: "#0f172a",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
