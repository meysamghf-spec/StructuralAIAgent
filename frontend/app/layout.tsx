import { AppProviders } from "@/components/AppProviders";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SAIA — Chat with your structural AI",
  description: "SAIA — chat with your structural AI: analysis, design, validation, approval and memory in one conversation",
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
