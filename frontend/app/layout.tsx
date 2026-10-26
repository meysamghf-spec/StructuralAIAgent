import { AppProviders } from "@/components/AppProviders";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "STRAI — Engineering Workspace",
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
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
