import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google"; // 1. Import fonts
import "./globals.css";
import { cn } from "@/lib/utils";

// 2. Configure font subsets and variable names
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const playfair = Playfair_Display({ subsets: ["latin"], variable: "--font-playfair-display" });

export const metadata: Metadata = {
  title: "Teeks | The Executive Assistant's Desk",
  description: "Chaos Out. Clarity In.",
};

import { AuthProvider } from "@/context/AuthContext";
import QueryProvider from "@/providers/QueryProvider";
import { Toaster } from "sonner";

import { ChatProvider } from "@/context/ChatContext";
import { OmniChatOverlay } from "@/components/chat/OmniChatOverlay";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={cn(
        "min-h-screen bg-background font-sans antialiased",
        inter.variable,
        playfair.variable
      )}>
        <QueryProvider>
          <AuthProvider>
            <ChatProvider>
              {children}
              <OmniChatOverlay />
              <Toaster position="bottom-right" />
            </ChatProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
