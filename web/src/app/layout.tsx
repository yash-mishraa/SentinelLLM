import React from "react";
import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/layout/header";

export const metadata: Metadata = {
  title: "SentinelLLM — Security boundaries for LLM-powered systems",
  description:
    "An open-source security gateway that inspects untrusted inputs, enforces tool-use policies, gates sensitive actions behind human approval, and records security decisions for inspection.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <body className="bg-background text-foreground min-h-screen flex flex-col font-sans antialiased selection:bg-[#a3e635]/20 selection:text-[#a3e635]">
        <Header />
        <main className="flex-1 flex flex-col w-full">{children}</main>
      </body>
    </html>
  );
}
