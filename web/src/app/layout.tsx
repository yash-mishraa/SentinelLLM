import React from "react";
import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/layout/header";

export const metadata: Metadata = {
  title: "SentinelLLM — Security boundary for LLM-powered systems",
  description:
    "An open-source security gateway that inspects untrusted inputs, enforces deterministic policies at the tool boundary, gates sensitive actions behind human approval, and records security decisions for inspection.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground min-h-screen flex flex-col font-sans antialiased">
        <Header />
        <main className="flex-1 flex flex-col w-full">{children}</main>
      </body>
    </html>
  );
}
