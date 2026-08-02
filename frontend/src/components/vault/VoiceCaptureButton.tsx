"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { Mic, MicOff, Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { createVoiceContextCapture } from "@/services/voice";
import { type DiaryCaptureScopeType, type DiaryContextEntry } from "@/services/vault";

const RECORD_LIMIT_SECONDS = 45;

type RecordState = "idle" | "recording" | "transcribing" | "done";

interface VoiceCaptureButtonProps {
  scopeType: DiaryCaptureScopeType;
  scopeId?: string | null;
  linkedTo?: string | null;
  isPro: boolean;
  /** Disable triggering a new recording (e.g. while a text save is in flight) */
  disabled?: boolean;
  onCaptureSaved: (entry: DiaryContextEntry) => void;
  className?: string;
}

export function VoiceCaptureButton({
  scopeType,
  scopeId,
  linkedTo,
  isPro,
  disabled = false,
  onCaptureSaved,
  className,
}: VoiceCaptureButtonProps) {
  const [recordState, setRecordState] = useState<RecordState>("idle");
  const [secondsLeft, setSecondsLeft] = useState(RECORD_LIMIT_SECONDS);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const doneTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSavedRef = useRef(onCaptureSaved);
  onSavedRef.current = onCaptureSaved;

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const releaseStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const submitRecording = useCallback(
    async (chunks: Blob[]) => {
      clearTimer();
      releaseStream();
      setRecordState("transcribing");

      const mimeType = chunks[0]?.type || "audio/webm";
      const ext = mimeType.includes("mp4") ? "mp4" : "webm";
      const blob = new Blob(chunks, { type: mimeType });

      try {
        const entry = await createVoiceContextCapture(blob, `capture.${ext}`, {
          scope_type: scopeType,
          scope_id: scopeId,
          linked_to: linkedTo,
        });
        setRecordState("done");
        onSavedRef.current(entry);
        toast("Got it.");
        doneTimerRef.current = setTimeout(() => setRecordState("idle"), 1500);
      } catch (err: unknown) {
        setRecordState("idle");
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 429) {
          toast.error("Voice memory is busy right now. Try again in a moment.");
        } else if (status === 502) {
          toast.error("Teeks couldn't hear that clearly. Try again.");
        } else {
          toast.error("That didn't save. Try again.");
        }
      }
    },
    [clearTimer, releaseStream, scopeType, scopeId, linkedTo]
  );

  const stopRecording = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }, []);

  const startRecording = useCallback(async () => {
    if (!isPro) {
      toast("Voice memory is a Pro feature.");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      toast.error("Microphone access was denied.");
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType });
    } catch {
      releaseStream();
      toast.error("Recording isn't supported on this browser.");
      return;
    }
    recorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => void submitRecording(chunksRef.current);

    recorder.start(250);
    setRecordState("recording");
    setSecondsLeft(RECORD_LIMIT_SECONDS);

    timerRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          stopRecording();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [isPro, submitRecording, stopRecording]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      clearTimer();
      releaseStream();
      if (doneTimerRef.current) clearTimeout(doneTimerRef.current);
    };
  }, [clearTimer, releaseStream]);

  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  // ── Transcribing ──────────────────────────────────────────────────────────
  if (recordState === "transcribing") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-[12px] text-muted-foreground font-inter select-none",
          className
        )}
      >
        <Loader2 size={13} className="animate-spin shrink-0" />
        Understanding…
      </span>
    );
  }

  // ── Done ─────────────────────────────────────────────────────────────────
  if (recordState === "done") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-[12px] text-muted-foreground font-inter select-none",
          className
        )}
      >
        <CheckCircle2 size={13} className="text-accent shrink-0" />
        Remembered
      </span>
    );
  }

  // ── Listening ─────────────────────────────────────────────────────────────
  if (recordState === "recording") {
    return (
      <div className={cn("inline-flex items-center gap-2", className)}>
        <span className="text-[12px] font-medium tabular-nums text-destructive font-inter select-none">
          {fmt(secondsLeft)}
        </span>
        <button
          type="button"
          onClick={stopRecording}
          className="inline-flex items-center justify-center rounded-[8px] bg-destructive px-3 py-2 text-white transition-all hover:brightness-95 active:scale-[0.97]"
          title="Stop listening"
          aria-label={`Listening. ${fmt(secondsLeft)} remaining. Tap to stop.`}
        >
          <MicOff size={14} />
        </button>
      </div>
    );
  }

  // ── Idle ─────────────────────────────────────────────────────────────────
  return (
    <button
      type="button"
      onClick={isPro && !disabled ? () => void startRecording() : () => toast("Voice memory is a Pro feature.")}
      disabled={disabled && isPro}
      title={isPro ? "Record a voice memory" : "Voice memory requires Pro"}
      className={cn(
        "inline-flex items-center justify-center rounded-[8px] border px-3 py-2 transition-all",
        isPro
          ? "border-border text-muted-foreground hover:text-foreground hover:border-border/80 active:scale-[0.97]"
          : "border-border/40 text-muted-foreground/35 cursor-default",
        className
      )}
      aria-label="Record a voice memory"
    >
      <Mic size={14} />
    </button>
  );
}
