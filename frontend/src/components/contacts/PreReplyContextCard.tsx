"use client";

import { useContactByEmail } from "@/hooks/useVault";
import { useContactBrief } from "@/hooks/useContacts";
import { AlertTriangle, Info, User } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface PreReplyContextCardProps {
  senderEmail: string;
  senderName?: string;
}

// Severity → visual treatment (design system: slate = informational, carmine = urgent)
const SIGNAL_STYLES: Record<string, string> = {
  urgent: "text-destructive",
  warning: "text-secondary",
  info: "text-accent",
};

export function PreReplyContextCard({ senderEmail, senderName }: PreReplyContextCardProps) {
  const { data: contact, isLoading: contactLoading } = useContactByEmail(senderEmail || null);
  const contactId = contact?.id ?? null;
  const { data: brief, isLoading: briefLoading } = useContactBrief(contactId);

  // Silent — don't render if no contact record
  if (contactLoading || briefLoading) return null;
  if (!contact || !brief) return null;

  const openCommitments = brief.commitments.filter(
    (c) => c.status !== "resolved" && c.status !== "completed"
  );
  const urgentSignals = brief.signals.filter((s) => s.severity === "urgent" || s.severity === "warning");
  const preferredTone = brief.summary.preferred_tone;

  return (
    <div
      className="rounded-[10px] border border-accent/20 bg-accent/[0.03] px-3.5 py-3 space-y-1.5"
      style={{ borderLeftWidth: "3px", borderLeftColor: "hsl(var(--accent))" }}
    >
      {/* Identity row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <User size={12} className="text-accent shrink-0" />
          <p className="text-[12px] font-semibold text-foreground font-inter truncate">
            {brief.contact.name || senderName}
          </p>
          {(brief.contact.role || brief.contact.organization) && (
            <p className="text-[11px] text-muted-foreground font-inter truncate hidden sm:block">
              {[brief.contact.role, brief.contact.organization].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Link
            href={`/dashboard/people/${contact.id}#capture-context`}
            className="inline-flex items-center rounded-full border border-border/70 bg-background/70 px-2.5 py-1 text-[11px] font-medium text-foreground hover:border-border hover:bg-background font-inter transition-colors whitespace-nowrap"
          >
            Capture context
          </Link>
          <Link
            href={`/dashboard/people/${contact.id}`}
            className="text-[11px] font-medium text-accent hover:underline underline-offset-2 font-inter transition-colors whitespace-nowrap"
          >
            View profile
          </Link>
        </div>
      </div>

      {/* Context pills */}
      {(openCommitments.length > 0 || preferredTone || urgentSignals.length > 0) && (
        <div className="flex flex-wrap items-center gap-2">
          {openCommitments.length > 0 && (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground font-inter">
              <span className="w-1 h-1 rounded-full bg-secondary shrink-0" />
              {openCommitments.length} open {openCommitments.length === 1 ? "commitment" : "commitments"}
            </span>
          )}
          {preferredTone && (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground font-inter">
              <span className="w-1 h-1 rounded-full bg-accent shrink-0" />
              Tone: {preferredTone}
            </span>
          )}
          {urgentSignals.map((signal) => (
            <span
              key={signal.key}
              className={cn(
                "inline-flex items-center gap-1 text-[11px] font-medium font-inter",
                SIGNAL_STYLES[signal.severity] ?? "text-muted-foreground"
              )}
            >
              {signal.severity === "urgent" ? (
                <AlertTriangle size={10} />
              ) : (
                <Info size={10} />
              )}
              {signal.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
