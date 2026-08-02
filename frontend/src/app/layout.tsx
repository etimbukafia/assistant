import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google"; // 1. Import fonts
import "./globals.css";
import { cn } from "@/lib/utils";

// 2. Configure font subsets and variable names
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const playfair = Playfair_Display({ subsets: ["latin"], variable: "--font-playfair-display" });

export const metadata: Metadata = {
  title: "Teeks | Automation powered by stored context",
  description: "Memory and automation for Executive Assistants.",
};

import { AuthProvider } from "@/context/AuthContext";
import QueryProvider from "@/providers/QueryProvider";
import { Toaster } from "sonner";

import { ChatProvider } from "@/context/ChatContext";
import { OmniChatOverlay } from "@/components/chat/OmniChatOverlay";
import { StickyNoteWidget } from "@/components/vault/StickyNoteWidget";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head />
      <body className={cn(
        "min-h-screen bg-background font-sans antialiased",
        inter.variable,
        playfair.variable
      )}>
        <QueryProvider>
          <AuthProvider>
            <ChatProvider>
              {children}
              <StickyNoteWidget />
              <OmniChatOverlay />
              <Toaster position="bottom-left" />
            </ChatProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
