"use client";

import { useState } from "react";
import { useDiaryContacts } from "@/hooks/useVault";
import { type DiaryContact } from "@/services/vault";
import { Search, Star, Briefcase, Globe, ShoppingCart, ChevronRight, Users } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

// ── Category config ──────────────────────────────────────────────────────────

type ContactCategory = "vip" | "colleague" | "external" | "vendor";

const CATEGORY_CONFIG: Record<ContactCategory, {
  label: string;
  icon: typeof Star;
  classes: string;
}> = {
  vip:      { label: "VIP",      icon: Star,         classes: "text-secondary bg-secondary/10 border-secondary/25" },
  colleague:{ label: "Colleague",icon: Briefcase,    classes: "text-accent bg-accent/10 border-accent/20" },
  external: { label: "External", icon: Globe,        classes: "text-copper bg-copper/10 border-copper/25" },
  vendor:   { label: "Vendor",   icon: ShoppingCart, classes: "text-muted-foreground bg-muted border-border" },
};

// VIPs float to the top
const CATEGORY_ORDER: Record<string, number> = { vip: 0, colleague: 1, external: 2, vendor: 3 };

function sortContacts(contacts: DiaryContact[]): DiaryContact[] {
  return [...contacts].sort((a, b) => {
    const wa = CATEGORY_ORDER[a.category ?? ""] ?? 4;
    const wb = CATEGORY_ORDER[b.category ?? ""] ?? 4;
    if (wa !== wb) return wa - wb;
    return a.name.localeCompare(b.name);
  });
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

// ── Sub-components ───────────────────────────────────────────────────────────

function CategoryBadge({ category }: { category: string | null | undefined }) {
  if (!category || !(category in CATEGORY_CONFIG)) return null;
  const { label, icon: Icon, classes } = CATEGORY_CONFIG[category as ContactCategory];
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium font-inter", classes)}>
      <Icon size={10} />
      {label}
    </span>
  );
}

function ContactCard({ contact }: { contact: DiaryContact }) {
  const initials = getInitials(contact.name);
  const subtitle = [contact.role, contact.organization].filter(Boolean).join(" · ");

  return (
    <Link
      href={`/dashboard/people/${contact.id}`}
      className="group flex items-center gap-3 rounded-[14px] border border-border bg-card px-4 py-3.5 transition-shadow hover:shadow-sm"
      style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)" }}
    >
      {/* Avatar */}
      <div className="w-9 h-9 rounded-full bg-copper/15 flex items-center justify-center text-copper text-[13px] font-bold font-inter shrink-0">
        {initials}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold text-foreground font-inter truncate leading-snug">
          {contact.name}
        </p>
        {subtitle && (
          <p className="text-[12px] text-muted-foreground font-inter truncate mt-0.5">
            {subtitle}
          </p>
        )}
      </div>

      {/* Category + chevron */}
      <div className="flex items-center gap-2 shrink-0">
        <CategoryBadge category={contact.category} />
        <ChevronRight size={14} className="text-muted-foreground/40 group-hover:text-muted-foreground transition-colors" />
      </div>
    </Link>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-[14px] border border-border bg-card px-4 py-3.5 flex items-center gap-3 animate-pulse">
      <div className="w-9 h-9 rounded-full bg-muted-foreground/10 shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 w-32 rounded bg-muted-foreground/10" />
        <div className="h-3 w-20 rounded bg-muted-foreground/8" />
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PeoplePage() {
  const [search, setSearch] = useState("");
  const { data: contacts, isLoading } = useDiaryContacts(search || undefined);

  const sorted = contacts ? sortContacts(contacts) : [];

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-playfair text-[28px] font-semibold text-foreground leading-tight">
          People
        </h1>
        {contacts && contacts.length > 0 && (
          <p className="text-[12px] text-muted-foreground font-inter">
            {contacts.length} {contacts.length === 1 ? "contact" : "contacts"}
          </p>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          placeholder="Search people"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-sm pl-8 pr-3 py-2 rounded-[8px] border border-border bg-background text-[13px] font-inter text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary transition-colors"
        />
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : sorted.length > 0 ? (
        <div className="space-y-2">
          {sorted.map((contact) => (
            <ContactCard key={contact.id} contact={contact} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
          <Users size={32} className="text-muted-foreground/30" />
          <p className="text-[14px] text-muted-foreground font-inter">
            {search ? "No contacts match that search." : "Your contacts appear here."}
          </p>
          {!search && (
            <p className="text-[12px] text-muted-foreground/60 font-inter max-w-xs">
              Add contacts from any inbox thread using the contact button on a message.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
