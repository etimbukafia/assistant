"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { formatDistanceToNow, parseISO } from "date-fns";
import { toast } from "sonner";
import { Link2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDiaryEntries, useDiaryMutations } from "@/hooks/useVault";
import { useAuth } from "@/context/AuthContext";
import { VoiceCaptureButton } from "./VoiceCaptureButton";
import {
  CONTEXT_CAPTURE_MAX_CHARS,
  type DiaryCaptureScopeType,
  type DiaryContextEntry,
  type DiaryEntryType,
} from "@/services/vault";

const CATEGORY_OPTIONS: Array<{ value: DiaryEntryType; label: string }> = [
  { value: "decision", label: "Decision" },
  { value: "risk", label: "Risk" },
  { value: "commitment", label: "Commitment" },
  { value: "preference", label: "Preference" },
  { value: "insight", label: "Insight" },
];

const UNCERTAIN_THRESHOLD = 0.7;

function computeStarters(scopeType: string, linkedTo: string | null | undefined): string[] {
  const firstName = linkedTo ? linkedTo.trim().split(/\s+/)[0] : null;
  switch (scopeType) {
    case "contact":
      return firstName
        ? [`${firstName} approved `, `${firstName} prefers `, `Committed to ${firstName} that `, "Watch out: "]
        : ["Decision made: ", "They prefer ", "Committed to them that ", "Watch out: "];
    case "message":
      return ["Decision made: ", "They prefer ", "Watch out: ", "Agreed to "];
    case "task":
      return ["Decision made: ", "Risk: ", "Blocked by ", "Watch out: "];
    case "event":
      return ["Decision made: ", "Agreed to ", "Action item: ", "Watch out: "];
    default:
      return ["Decision made: ", "CEO prefers ", "Watch out: ", "Risk: "];
  }
}

interface InlineContextCaptureCardProps {
  scopeType: Exclude<DiaryCaptureScopeType, "global">;
  scopeId: string | number | null | undefined;
  linkedTo?: string | null;
  heading?: string;
  description: string;
  placeholder: string;
  saveLabel?: string;
  className?: string;
  revealStoredCaptureByDefault?: boolean;
  allowStoredCaptureCorrection?: boolean;
}

export function InlineContextCaptureCard({
  scopeType,
  scopeId,
  linkedTo,
  heading = "Remember this",
  description,
  placeholder,
  saveLabel = "Remember",
  className,
  revealStoredCaptureByDefault = true,
  allowStoredCaptureCorrection = true,
}: InlineContextCaptureCardProps) {
  const [captureText, setCaptureText] = useState("");
  const [recentCaptureId, setRecentCaptureId] = useState<number | null>(null);
  const [recentCaptureFallback, setRecentCaptureFallback] = useState<DiaryContextEntry | null>(null);
  const [storedCaptureRevealed, setStoredCaptureRevealed] = useState(revealStoredCaptureByDefault);
  const [showCorrectionPicker, setShowCorrectionPicker] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const starters = useMemo(() => computeStarters(scopeType, linkedTo), [scopeType, linkedTo]);

  const applyStarter = (starter: string) => {
    setCaptureText(starter);
    setTimeout(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(starter.length, starter.length);
    }, 0);
  };

  const normalizedScopeId = scopeId == null ? null : String(scopeId);
  const { settings } = useAuth();
  const isPro = settings?.subscription_tier === "pro";
  const { createEntry, correctCategory, removeCaptureLink } = useDiaryMutations();
  const { data: scopedEntries = [] } = useDiaryEntries(
    normalizedScopeId
      ? { entity_type: scopeType, entity_id: normalizedScopeId }
      : undefined,
    {
      refetchInterval:
        recentCaptureId && recentCaptureFallback?.classification_status === "pending"
          ? 5_000
          : false,
    }
  );

  const latestScopedCapture = useMemo(() => {
    if (!scopedEntries.length) return null;
    return scopedEntries[0] ?? null;
  }, [scopedEntries]);

  const recentCapture = useMemo(() => {
    if (!recentCaptureId) return latestScopedCapture;
    return (
      scopedEntries.find((entry) => entry.id === recentCaptureId) ??
      recentCaptureFallback ??
      latestScopedCapture
    );
  }, [latestScopedCapture, recentCaptureFallback, recentCaptureId, scopedEntries]);

  const recentCaptureIsPending = recentCapture?.classification_status === "pending";
  const recentCaptureIsUncertain =
    recentCapture?.classification_status === "classified" &&
    typeof recentCapture.classification_confidence === "number" &&
    recentCapture.classification_confidence < UNCERTAIN_THRESHOLD;
  const isSessionCapture = !!recentCaptureId && recentCapture?.id === recentCaptureId;
  const shouldRevealCapture =
    !!recentCapture &&
    (isSessionCapture || revealStoredCaptureByDefault || storedCaptureRevealed);
  const canCorrectInline =
    !!recentCapture &&
    !recentCaptureIsPending &&
    (isSessionCapture || allowStoredCaptureCorrection);
  const userLinks = useMemo(
    () => (recentCapture?.links ?? []).filter((link) => (link.source || "user") !== "teeks"),
    [recentCapture?.links]
  );
  const teeksLinks = useMemo(
    () => (recentCapture?.links ?? []).filter((link) => link.source === "teeks"),
    [recentCapture?.links]
  );

  useEffect(() => {
    if (!recentCaptureId) return;
    const matched = scopedEntries.find((entry) => entry.id === recentCaptureId);
    if (matched) {
      setRecentCaptureFallback(matched);
      return;
    }
    if (recentCaptureFallback?.id === recentCaptureId && recentCaptureFallback.classification_status !== "pending") {
      setRecentCaptureFallback(null);
      setRecentCaptureId(null);
    }
  }, [recentCaptureFallback, recentCaptureId, scopedEntries]);

  useEffect(() => {
    if (revealStoredCaptureByDefault) {
      setStoredCaptureRevealed(true);
    }
  }, [revealStoredCaptureByDefault]);

  // Close correction picker if the active capture changes beneath it
  useEffect(() => {
    setShowCorrectionPicker(false);
  }, [recentCapture?.id]);

  const handleCapture = async () => {
    const trimmed = captureText.trim();
    if (!trimmed || !normalizedScopeId) return;
    if (trimmed.length > CONTEXT_CAPTURE_MAX_CHARS) {
      toast.error(`Keep this under ${CONTEXT_CAPTURE_MAX_CHARS} characters.`);
      return;
    }

    try {
      const created = await createEntry.mutateAsync({
        text: trimmed,
        scope_type: scopeType,
        scope_id: normalizedScopeId,
        linked_to: linkedTo ?? null,
      });
      setRecentCaptureId(created.id);
      setRecentCaptureFallback(created);
      setStoredCaptureRevealed(true);
      setShowCorrectionPicker(false);
      setCaptureText("");
      toast("Got it.");
    } catch {
      toast.error("Didn't save. Try again.");
    }
  };

  const handleCorrectCategory = async (category: DiaryEntryType) => {
    if (!recentCapture) return;
    setShowCorrectionPicker(false);
    try {
      const updated = await correctCategory.mutateAsync({ id: recentCapture.id, category });
      setRecentCaptureFallback(updated);
      toast(`Remembered as ${category}.`);
    } catch {
      toast.error("That change didn't save. Try again.");
    }
  };

  const handleRemoveLink = async (entityType: string, entityId: string) => {
    if (!recentCapture) return;
    try {
      const updated = await removeCaptureLink.mutateAsync({
        id: recentCapture.id,
        entityType,
        entityId,
      });
      setRecentCaptureFallback(updated);
      toast("Link removed.");
    } catch {
      toast.error("That link change didn't save. Try again.");
    }
  };

  return (
    <div
      className={cn("rounded-[12px] border border-border bg-card px-4 py-4 space-y-3", className)}
      style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)" }}
    >
      <div className="space-y-1">
        <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
          {heading}
        </p>
        <p className="text-[13px] text-muted-foreground font-inter leading-relaxed">
          {description}
        </p>
      </div>

      {!captureText && (
        <div className="flex flex-wrap gap-1.5">
          {starters.map((starter) => (
            <button
              key={starter}
              type="button"
              onClick={() => applyStarter(starter)}
              className="inline-flex items-center rounded-full border border-border/60 bg-background px-2.5 py-1 text-[11px] text-muted-foreground font-inter hover:border-border hover:text-foreground transition-colors"
            >
              {starter.trimEnd()}…
            </button>
          ))}
        </div>
      )}

      <textarea
        ref={textareaRef}
        value={captureText}
        onChange={(e) => setCaptureText(e.target.value)}
        maxLength={CONTEXT_CAPTURE_MAX_CHARS}
        placeholder={placeholder}
        rows={3}
        className="w-full resize-none rounded-[12px] border border-border bg-background px-3 py-2.5 text-[15px] font-inter text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary transition-colors"
      />

      <div className="flex items-center justify-between gap-3">
        <div className="space-y-0.5">
          <p className="text-[12px] text-muted-foreground font-inter">
            Teeks will hold onto this.
          </p>
          <p className="text-[11px] text-muted-foreground/60 font-inter">
            {captureText.length}/{CONTEXT_CAPTURE_MAX_CHARS}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <VoiceCaptureButton
            scopeType={scopeType}
            scopeId={normalizedScopeId}
            linkedTo={linkedTo}
            isPro={isPro}
            disabled={createEntry.isPending}
            onCaptureSaved={(entry) => {
              setRecentCaptureId(entry.id);
              setRecentCaptureFallback(entry);
              setStoredCaptureRevealed(true);
              setShowCorrectionPicker(false);
              setCaptureText("");
            }}
          />
          <button
            type="button"
            onClick={() => void handleCapture()}
            disabled={!captureText.trim() || createEntry.isPending || !normalizedScopeId}
            className="inline-flex items-center justify-center rounded-[8px] bg-secondary px-4 py-2 text-[13px] font-semibold text-white font-inter transition-all hover:brightness-105 active:scale-[0.97] disabled:opacity-40"
          >
            {createEntry.isPending ? "Saving..." : saveLabel}
          </button>
        </div>
      </div>

      {/* Collapsed preview */}
      {recentCapture && !shouldRevealCapture && (
        <div className="rounded-[12px] border border-border/70 bg-background px-3.5 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-[11px] font-bold uppercase tracking-[1.1px] text-muted-foreground font-inter">
                Last remembered
              </p>
              <p className="text-[12px] text-muted-foreground font-inter">
                {recentCaptureIsPending
                  ? "Teeks is still filing this away."
                  : recentCaptureIsUncertain
                    ? "Filed as Insight — Teeks wasn't certain."
                    : `Remembered as ${recentCapture.type}.`}
              </p>
              <p className="text-[11px] text-muted-foreground/60 font-inter">
                {formatDistanceToNow(parseISO(recentCapture.updated_at || recentCapture.created_at), {
                  addSuffix: true,
                })}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setStoredCaptureRevealed(true)}
              className="inline-flex items-center rounded-full border border-border bg-card px-2.5 py-1 text-[11px] font-medium text-foreground hover:border-border/80 transition-colors"
            >
              Reveal
            </button>
          </div>
        </div>
      )}

      {/* Expanded view */}
      {recentCapture && shouldRevealCapture && (
        <div className="rounded-[12px] border border-border/70 bg-background px-3.5 py-3 space-y-2.5">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-[11px] font-bold uppercase tracking-[1.1px] text-muted-foreground font-inter">
                Last remembered
              </p>
              <p className="text-[13px] text-foreground font-inter leading-relaxed">
                {recentCapture.content}
              </p>
              {!isSessionCapture && (
                <p className="text-[11px] text-muted-foreground/60 font-inter">
                  {formatDistanceToNow(parseISO(recentCapture.updated_at || recentCapture.created_at), {
                    addSuffix: true,
                  })}
                </p>
              )}
            </div>
            <span
              className={cn(
                "inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[1.1px] font-inter shrink-0",
                recentCaptureIsPending
                  ? "border-secondary/40 bg-secondary/[0.08] text-secondary"
                  : "border-accent/20 bg-accent/[0.04] text-accent"
              )}
            >
              {recentCaptureIsPending ? "Remembering" : recentCapture.type}
            </span>
          </div>

          <div className="space-y-2">
            {recentCaptureIsPending ? (
              <p className="text-[12px] text-muted-foreground font-inter">
                Teeks is filing this away now.
              </p>
            ) : canCorrectInline ? (
              showCorrectionPicker ? (
                <div className="space-y-1.5">
                  <p className="text-[11px] text-muted-foreground/70 font-inter">What is it?</p>
                  <div className="flex flex-wrap gap-1.5">
                    {CATEGORY_OPTIONS.filter((o) => o.value !== recentCapture.type).map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => void handleCorrectCategory(option.value)}
                        disabled={correctCategory.isPending}
                        className="inline-flex items-center rounded-full border border-border bg-card px-2.5 py-1 text-[11px] font-medium text-muted-foreground hover:text-foreground hover:border-border/80 transition-colors disabled:opacity-50"
                      >
                        {option.label}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => setShowCorrectionPicker(false)}
                      className="inline-flex items-center rounded-full border border-border/50 bg-card px-2.5 py-1 text-[11px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-[12px] text-muted-foreground font-inter">
                  {recentCaptureIsUncertain
                    ? "Teeks wasn't sure how to file this."
                    : <>Remembered as <span className="font-medium text-foreground capitalize">{recentCapture.type}</span>.</>}{" "}
                  <button
                    type="button"
                    onClick={() => setShowCorrectionPicker(true)}
                    className="text-muted-foreground/60 hover:text-foreground underline underline-offset-2 transition-colors"
                  >
                    Not right?
                  </button>
                </p>
              )
            ) : (
              <p className="text-[12px] text-muted-foreground font-inter">
                Remembered as <span className="font-medium text-foreground capitalize">{recentCapture.type}</span>.
              </p>
            )}

            {(userLinks.length > 0 || teeksLinks.length > 0) && (
              <div className="space-y-1.5 pt-1">
                <p className="text-[11px] font-bold uppercase tracking-[1.1px] text-muted-foreground font-inter">
                  Linked context
                </p>
                {userLinks.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-[11px] text-muted-foreground/70 font-inter">You linked</p>
                    <div className="flex flex-wrap gap-1.5">
                      {userLinks.map((link) => (
                        <span
                          key={`${link.entity_type}:${link.entity_id}`}
                          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-[11px] font-medium text-muted-foreground"
                        >
                          <Link2 size={11} className="text-muted-foreground/70" />
                          <span className="truncate max-w-[160px]">{link.display_name}</span>
                          <button
                            type="button"
                            onClick={() => void handleRemoveLink(link.entity_type, link.entity_id)}
                            disabled={removeCaptureLink.isPending}
                            className="rounded-full text-muted-foreground/70 hover:text-foreground transition-colors disabled:opacity-50"
                            aria-label={`Remove link to ${link.display_name}`}
                            title="Remove link"
                          >
                            <X size={11} />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {teeksLinks.length > 0 && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="text-[11px] text-muted-foreground/70 font-inter">Teeks also linked</p>
                      {isSessionCapture && !recentCaptureIsPending && (
                        <span className="inline-flex items-center rounded-full border border-accent/20 bg-accent/[0.05] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[1px] text-accent font-inter">
                          New
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {teeksLinks.map((link) => (
                        <span
                          key={`${link.entity_type}:${link.entity_id}`}
                          className="inline-flex items-center gap-1.5 rounded-full border border-accent/20 bg-accent/[0.03] px-2.5 py-1 text-[11px] font-medium text-foreground/80"
                        >
                          <Link2 size={11} className="text-accent" />
                          <span>{link.display_name}</span>
                          <button
                            type="button"
                            onClick={() => void handleRemoveLink(link.entity_type, link.entity_id)}
                            disabled={removeCaptureLink.isPending}
                            className="rounded-full text-muted-foreground/70 hover:text-foreground transition-colors disabled:opacity-50"
                            aria-label={`Remove link to ${link.display_name}`}
                            title="Remove link"
                          >
                            <X size={11} />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
