"use client";

import { cn } from "@/lib/utils";
import { type AutomationStatus, statusLabel } from "@/lib/automationCatalog";

export function AutomationStatusBadge({ status }: { status: AutomationStatus }) {
    return (
        <span
            className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-[1px]",
                status === "needs_connection" && "bg-amber-50 text-amber-700",
                status === "ready" && "bg-[#1F6B5C]/10 text-[#1F6B5C]",
                status === "running" && "bg-[#4D7C0F]/10 text-[#4D7C0F]",
                status === "drafts_only" && "bg-[#A07850]/10 text-[#A07850]",
                status === "off" && "bg-muted text-muted-foreground",
            )}
        >
            {status === "running" && (
                <span className="h-1.5 w-1.5 rounded-full bg-[#4D7C0F] animate-pulse" />
            )}
            {statusLabel(status)}
        </span>
    );
}
