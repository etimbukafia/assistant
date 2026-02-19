import type { Metadata } from "next";
import "./globals.css";
import { PlaygroundProvider } from "@/features/core/PlaygroundProvider";
import PlaygroundShell from "@/features/shell/PlaygroundShell";

export const metadata: Metadata = {
  title: "Playground - Things to Remember",
  description: "Playground UI for capturing context entries.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <PlaygroundProvider>
          <PlaygroundShell>{children}</PlaygroundShell>
        </PlaygroundProvider>
      </body>
    </html>
  );
}
