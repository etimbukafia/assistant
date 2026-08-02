"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useContactBrief, useContactTimeline } from "@/hooks/useContacts";
import { InlineContextCaptureCard } from "@/components/vault/InlineContextCaptureCard";
import {
  type ContactBriefCommitment,
  type ContactBriefDecision,
  type ContactBriefMemoryItem,
  type ContactBriefInteraction,
  type ContactBriefEvent,
  type ContactTimelineItem,
} from "@/services/contacts";
import {
  ArrowLeft, CheckCircle2, Clock, Mail, Calendar, FileText, Star, Briefcase, Globe, ShoppingCart,
} from "lucide-react";
import Link from "next/link";
import { format, parseISO, formatDistanceToNow } from "date-fns";
import { cn } from "@/lib/utils";

// ── Helpers ───────────────────────────────────────────────────────────────────

function getInitials(name: string): string {
  return name.split(" ").filter(Boolean).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
}

type Category = "vip" | "colleague" | "external" | "vendor";

const CATEGORY_CONFIG: Record<Category, { label: string; icon: typeof Star; classes: string }> = {
  vip:       { label: "VIP",       icon: Star,         classes: "text-secondary bg-secondary/10 border-secondary/25" },
  colleague: { label: "Colleague", icon: Briefcase,    classes: "text-accent bg-accent/10 border-accent/20" },
  external:  { label: "External",  icon: Globe,        classes: "text-copper bg-copper/10 border-copper/25" },
  vendor:    { label: "Vendor",    icon: ShoppingCart, classes: "text-muted-foreground bg-muted border-border" },
};

function CategoryBadge({ category }: { category: string | null | undefined }) {
  if (!category || !(category in CATEGORY_CONFIG)) return null;
  const { label, icon: Icon, classes } = CATEGORY_CONFIG[category as Category];
  return (
    <span className={cn("inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-[11px] font-medium font-inter", classes)}>
      <Icon size={11} />
      {label}
    </span>
  );
}

const TIMELINE_KIND_ICON: Record<string, typeof Mail> = {
  message:         Mail,
  meeting:         Calendar,
  task:            CheckCircle2,
  thread_decision: FileText,
  context_entry:   FileText,
};

// ── Sub-sections ──────────────────────────────────────────────────────────────

function CommitmentsSection({ commitments }: { commitments: ContactBriefCommitment[] }) {
  const open = commitments.filter((c) => c.status !== "resolved" && c.status !== "completed");
  if (open.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
        Open commitments
      </p>
      <div className="space-y-px">
        {open.map((c) => (
          <div key={c.id} className="py-2.5 border-b border-border/40 last:border-0 space-y-0.5">
            <p className="text-[13px] font-medium text-foreground font-inter">{c.title}</p>
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground/60 font-inter">
              {c.due_at && (
                <span className="flex items-center gap-1">
                  <Clock size={10} />
                  Due {format(parseISO(c.due_at), "MMM d")}
                </span>
              )}
              {c.detail && <span className="truncate max-w-[240px]">{c.detail}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DecisionsSection({ decisions }: { decisions: ContactBriefDecision[] }) {
  if (decisions.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
        Decisions made together
      </p>
      <div className="space-y-px">
        {decisions.slice(0, 5).map((d) => (
          <div key={d.id} className="py-2.5 border-b border-border/40 last:border-0">
            <p className="text-[13px] text-foreground font-inter leading-snug">{d.decision}</p>
            {d.created_at && (
              <p className="text-[11px] text-muted-foreground/50 font-inter mt-0.5">
                {formatDistanceToNow(parseISO(d.created_at), { addSuffix: true })}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PreferencesSection({ preferences }: { preferences: ContactBriefMemoryItem[] }) {
  if (preferences.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
        Preferences & sensitivities
      </p>
      <div className="space-y-px">
        {preferences.map((p) => (
          <div key={p.id} className="py-2 border-b border-border/40 last:border-0">
            <p className="text-[13px] text-foreground font-inter">{p.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentInteractionsSection({ interactions }: { interactions: ContactBriefInteraction[] }) {
  if (interactions.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
        Recent interactions
      </p>
      <div className="space-y-3">
        {interactions.slice(0, 5).map((i) => (
          <div key={i.id} className="flex items-start gap-2.5">
            <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center shrink-0 mt-0.5">
              <Mail size={11} className="text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-medium text-foreground font-inter truncate">
                {i.subject || `${i.interaction_type} interaction`}
              </p>
              {i.summary && (
                <p className="text-[12px] text-muted-foreground font-inter line-clamp-2 mt-0.5">
                  {i.summary}
                </p>
              )}
              <p className="text-[11px] text-muted-foreground/50 font-inter mt-0.5">
                {formatDistanceToNow(parseISO(i.occurred_at), { addSuffix: true })}
                {i.needs_reply && (
                  <span className="ml-2 text-secondary font-medium">· needs reply</span>
                )}
              </p>
            </div>
            {i.thread_id && i.thread_resolved !== false && (
              <Link
                href={`/dashboard/inbox?threadId=${encodeURIComponent(i.thread_id)}`}
                className="shrink-0 text-[11px] text-accent hover:underline underline-offset-2 font-inter"
              >
                Open
              </Link>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function UpcomingEventsSection({ events }: { events: ContactBriefEvent[] }) {
  if (events.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
        Upcoming meetings
      </p>
      <div className="space-y-2">
        {events.slice(0, 3).map((e) => (
          <div key={e.id} className="flex items-center gap-3">
            <Calendar size={13} className="text-muted-foreground shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-medium text-foreground font-inter truncate">{e.title}</p>
              <p className="text-[11px] text-muted-foreground/60 font-inter mt-0.5">
                {format(parseISO(e.start_time), "EEE, MMM d 'at' h:mm a")}
                {e.participant_count > 1 && ` · ${e.participant_count} attendees`}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Timeline ──────────────────────────────────────────────────────────────────

function TimelineView({ items }: { items: ContactTimelineItem[] }) {
  if (items.length === 0) {
    return (
      <p className="py-8 text-center text-[13px] text-muted-foreground font-inter">
        No timeline activity yet.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {items.map((item, idx) => {
        const Icon = TIMELINE_KIND_ICON[item.kind] ?? FileText;
        const isLast = idx === items.length - 1;
        return (
          <div key={item.id} className="flex items-start gap-3">
            <div className="flex flex-col items-center shrink-0">
              <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center">
                <Icon size={11} className="text-muted-foreground" />
              </div>
              {!isLast && <div className="w-px flex-1 min-h-[16px] bg-border/60 mt-1" />}
            </div>
            <div className={cn("flex-1 min-w-0 pb-3", isLast && "pb-0")}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-[13px] font-medium text-foreground font-inter leading-snug">
                  {item.title}
                </p>
                <p className="text-[11px] text-muted-foreground/50 font-inter shrink-0 mt-0.5">
                  {formatDistanceToNow(parseISO(item.occurred_at), { addSuffix: true })}
                </p>
              </div>
              {item.detail && (
                <p className="text-[12px] text-muted-foreground font-inter mt-0.5 line-clamp-2">
                  {item.detail}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-muted-foreground/10 shrink-0" />
        <div className="space-y-2 flex-1">
          <div className="h-7 w-44 rounded bg-muted-foreground/10" />
          <div className="h-3.5 w-28 rounded bg-muted-foreground/8" />
        </div>
      </div>
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-muted-foreground/10" />
        <div className="h-4 w-4/5 rounded bg-muted-foreground/8" />
        <div className="h-4 w-3/5 rounded bg-muted-foreground/7" />
      </div>
      <div className="h-3 w-48 rounded bg-muted-foreground/8" />
      <div className="h-px bg-border" />
      {[1, 2].map((i) => (
        <div key={i} className="space-y-2">
          <div className="h-3 w-24 rounded bg-muted-foreground/10" />
          <div className="h-4 w-3/4 rounded bg-muted-foreground/8" />
          <div className="h-4 w-2/3 rounded bg-muted-foreground/7" />
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "overview" | "timeline";

export default function ContactIntelligencePage() {
  const params = useParams();
  const contactId = params.id ? parseInt(params.id as string, 10) : null;

  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const { data: brief, isLoading, error } = useContactBrief(contactId);
  const { data: timeline, isLoading: timelineLoading } = useContactTimeline(
    activeTab === "timeline" ? contactId : null
  );

  if (isLoading) {
    return (
      <div className="max-w-2xl space-y-4">
        <div className="h-4 w-16 rounded bg-muted-foreground/10 animate-pulse" />
        <PageSkeleton />
      </div>
    );
  }

  if (error || !brief) {
    return (
      <div className="max-w-2xl space-y-4">
        <Link
          href="/dashboard/people"
          className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground font-inter transition-colors"
        >
          <ArrowLeft size={13} />
          People
        </Link>
        <p className="text-[14px] text-muted-foreground font-inter py-8">Contact not found.</p>
      </div>
    );
  }

  const { contact, summary, stats, signals, commitments, decisions, preferences, recent_interactions, upcoming_events } = brief;
  const initials = getInitials(contact.name);
  const lastContact = recent_interactions[0]?.occurred_at;

  const metaParts = [
    stats.total_threads > 0 && `${stats.total_threads} thread${stats.total_threads === 1 ? "" : "s"}`,
    stats.open_tasks > 0 && `${stats.open_tasks} open task${stats.open_tasks === 1 ? "" : "s"}`,
    lastContact && `last contact ${formatDistanceToNow(parseISO(lastContact), { addSuffix: true })}`,
  ].filter(Boolean);

  const tabBase = "px-3 py-1.5 rounded-full text-[12px] font-medium font-inter transition-all border";
  const tabActive = "bg-foreground text-background border-foreground";
  const tabIdle = "border-border text-muted-foreground hover:text-foreground hover:border-border/80";

  return (
    <div className="max-w-2xl space-y-6">

      {/* Back */}
      <Link
        href="/dashboard/people"
        className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground font-inter transition-colors"
      >
        <ArrowLeft size={13} />
        People
      </Link>

      {/* Identity */}
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-full bg-copper/15 flex items-center justify-center text-copper text-[16px] font-bold font-inter shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-playfair text-[26px] font-semibold text-foreground leading-tight">
              {contact.name}
            </h1>
            <CategoryBadge category={contact.category} />
          </div>
          {(contact.role || contact.organization) && (
            <p className="text-[13px] text-muted-foreground font-inter">
              {[contact.role, contact.organization].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
      </div>

      {/* Briefing — Teeks speaks first */}
      {(summary.headline || summary.relationship_notes.length > 0) && (
        <div className="space-y-2">
          {summary.headline && (
            <p className="text-[15px] text-foreground font-inter leading-relaxed">
              {summary.headline}
            </p>
          )}
          {summary.relationship_notes.length > 0 && (
            <ul className="space-y-1">
              {summary.relationship_notes.map((note, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px] text-muted-foreground font-inter leading-relaxed">
                  <span className="w-1 h-1 rounded-full bg-muted-foreground/30 mt-[7px] shrink-0" />
                  {note}
                </li>
              ))}
            </ul>
          )}
          {summary.preferred_tone && (
            <p className="text-[12px] text-muted-foreground/70 font-inter">
              Prefers <span className="text-foreground font-medium">{summary.preferred_tone}</span>.
            </p>
          )}
        </div>
      )}

      {/* Meta — one sentence */}
      {metaParts.length > 0 && (
        <p className="text-[12px] text-muted-foreground/60 font-inter">
          {metaParts.join(" · ")}
        </p>
      )}

      {/* Teeks noticed */}
      {signals.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
            Teeks noticed
          </p>
          <div className="space-y-1.5">
            {signals.map((signal) => (
              <p key={signal.key} className={cn(
                "text-[13px] font-inter leading-snug",
                signal.severity === "urgent" ? "text-destructive" :
                signal.severity === "warning" ? "text-secondary" :
                "text-muted-foreground"
              )}>
                {signal.label}{signal.detail ? ` — ${signal.detail}` : ""}
              </p>
            ))}
          </div>
        </div>
      )}

      <div className="h-px bg-border" />

      {/* Capture */}
      <InlineContextCaptureCard
        scopeType="contact"
        scopeId={contactId}
        linkedTo={contact.name}
        heading="What should Teeks remember?"
        description={`What do you want Teeks to remember about ${contact.name}?`}
        placeholder={`What matters about ${contact.name}?`}
        revealStoredCaptureByDefault={false}
      />

      <div className="h-px bg-border" />

      {/* Tabs */}
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => setActiveTab("overview")} className={cn(tabBase, activeTab === "overview" ? tabActive : tabIdle)}>
          Overview
        </button>
        <button type="button" onClick={() => setActiveTab("timeline")} className={cn(tabBase, activeTab === "timeline" ? tabActive : tabIdle)}>
          Timeline
        </button>
      </div>

      {/* Overview */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <CommitmentsSection commitments={commitments} />
          <DecisionsSection decisions={decisions} />
          <PreferencesSection preferences={preferences} />
          <RecentInteractionsSection interactions={recent_interactions} />
          <UpcomingEventsSection events={upcoming_events} />
          {summary.manual_notes && (
            <div className="space-y-2">
              <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Notes</p>
              <p className="text-[13px] text-muted-foreground font-inter whitespace-pre-wrap leading-relaxed">
                {summary.manual_notes}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Timeline */}
      {activeTab === "timeline" && (
        <div>
          {timelineLoading ? (
            <div className="animate-pulse space-y-4 py-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-muted-foreground/10 shrink-0" />
                  <div className="flex-1 space-y-1.5 pt-0.5">
                    <div className="h-3.5 w-48 rounded bg-muted-foreground/10" />
                    <div className="h-3 w-32 rounded bg-muted-foreground/8" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <TimelineView items={timeline?.timeline ?? []} />
          )}
        </div>
      )}

    </div>
  );
}
