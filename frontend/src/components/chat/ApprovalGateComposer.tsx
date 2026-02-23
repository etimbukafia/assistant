import * as React from "react";
import { Check, X } from "lucide-react";
import { PendingAction } from "@/services/chat";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

type IndexedAction = PendingAction & { index: number; label: string };

function actionLabel(action: PendingAction): string {
    const data = (action.action_data || {}) as Record<string, unknown>;
    const raw =
        (typeof data.title === "string" && data.title) ||
        (typeof data.subject === "string" && data.subject) ||
        (typeof data.intent === "string" && data.intent) ||
        "";
    const base = (action.action_type || "action").replace(/_/g, " ").trim();
    if (raw) return raw.trim();
    return base.charAt(0).toUpperCase() + base.slice(1);
}

function buildApprovalCommand(actions: IndexedAction[], selectedIds: Set<string>, note: string): string {
    const selected = actions.filter((item) => selectedIds.has(item.id)).map((item) => item.index);
    const unselected = actions.filter((item) => !selectedIds.has(item.id)).map((item) => item.index);
    const cleanedNote = note.trim();

    let command = "";
    if (selected.length === 0) {
        command = "cancel";
    } else if (selected.length === actions.length) {
        command = "approve all";
    } else {
        command = `run ${selected.join(" and ")}`;
        if (unselected.length > 0) {
            command += ` and skip ${unselected.join(" and ")}`;
        }
    }

    if (cleanedNote) {
        command += `. ${cleanedNote}`;
    }
    return command;
}

interface ApprovalGateComposerProps {
    pendingActions: PendingAction[];
    disabled?: boolean;
    onSendDecision: (command: string) => Promise<void>;
}

export function ApprovalGateComposer({ pendingActions, disabled, onSendDecision }: ApprovalGateComposerProps) {
    const actions = React.useMemo<IndexedAction[]>(
        () =>
            pendingActions.map((action, idx) => ({
                ...action,
                index: idx + 1,
                label: actionLabel(action),
            })),
        [pendingActions]
    );
    const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
    const [note, setNote] = React.useState("");
    const [isSubmitting, setIsSubmitting] = React.useState(false);

    React.useEffect(() => {
        setSelectedIds(new Set());
        setNote("");
    }, [pendingActions]);

    if (!actions.length) return null;

    const allSelected = selectedIds.size > 0 && selectedIds.size === actions.length;
    const effectiveDisabled = Boolean(disabled || isSubmitting);

    const toggle = (id: string) => {
        if (effectiveDisabled) return;
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const selectAll = () => {
        if (effectiveDisabled) return;
        setSelectedIds(new Set(actions.map((item) => item.id)));
    };

    const clearSelection = () => {
        if (effectiveDisabled) return;
        setSelectedIds(new Set());
    };

    const sendDecision = async () => {
        if (effectiveDisabled) return;
        const command = buildApprovalCommand(actions, selectedIds, note);
        setIsSubmitting(true);
        try {
            await onSendDecision(command);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="mb-3 rounded-[12px] border border-border bg-linen/40 p-3">
            <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                    Approval
                </p>
                <div className="flex items-center gap-1.5">
                    <button
                        type="button"
                        onClick={selectAll}
                        disabled={effectiveDisabled}
                        className="rounded-full border border-border bg-white px-2.5 py-1 text-[11px] text-foreground hover:bg-linen disabled:opacity-50 font-inter"
                    >
                        Select all
                    </button>
                    <button
                        type="button"
                        onClick={clearSelection}
                        disabled={effectiveDisabled || selectedIds.size === 0}
                        className="rounded-full border border-border bg-white px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-linen disabled:opacity-50 font-inter"
                    >
                        Clear
                    </button>
                </div>
            </div>

            <div className="mt-2 flex flex-wrap gap-1.5">
                {actions.map((action) => {
                    const selected = selectedIds.has(action.id);
                    return (
                        <button
                            key={action.id}
                            type="button"
                            onClick={() => toggle(action.id)}
                            disabled={effectiveDisabled}
                            className={cn(
                                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-inter transition",
                                selected
                                    ? "border-primary/35 bg-primary/[0.09] text-primary"
                                    : "border-border bg-white text-foreground hover:bg-linen"
                            )}
                        >
                            <span className="text-[10px] rounded-full bg-black/5 px-1.5 py-0.5">
                                {action.index}
                            </span>
                            <span className="max-w-[240px] truncate">{action.label}</span>
                            {selected ? <Check size={11} /> : null}
                        </button>
                    );
                })}
            </div>

            <div className="mt-2.5 flex items-center gap-2">
                <Input
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Optional instruction for selected actions"
                    className="h-9 text-xs bg-white"
                    disabled={effectiveDisabled}
                />
                <button
                    type="button"
                    onClick={sendDecision}
                    disabled={effectiveDisabled}
                    className="h-9 rounded-[8px] bg-primary px-3 text-xs font-semibold text-white hover:bg-primary/90 disabled:opacity-40 font-inter"
                >
                    Send
                </button>
                <button
                    type="button"
                    onClick={async () => {
                        if (effectiveDisabled) return;
                        setIsSubmitting(true);
                        try {
                            await onSendDecision(note.trim() ? `cancel. ${note.trim()}` : "cancel");
                        } finally {
                            setIsSubmitting(false);
                        }
                    }}
                    disabled={effectiveDisabled}
                    className="h-9 rounded-[8px] border border-border bg-white px-3 text-xs text-muted-foreground hover:bg-linen disabled:opacity-40 font-inter"
                >
                    <X size={12} className="inline mr-1" />
                    Cancel all
                </button>
            </div>
            {allSelected ? (
                <p className="mt-2 text-[11px] text-muted-foreground font-inter">All actions selected.</p>
            ) : null}
        </div>
    );
}
