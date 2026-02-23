"use client";

import { useEffect, useState } from "react";
import { createChatSession, fetchMentionSuggestions, sendChatMessageV1, streamChatMessage } from "../core/api";
import { usePlayground } from "../core/PlaygroundProvider";
import type {
  ChatMessage,
  MentionChip,
  MentionSuggestion,
} from "../core/types";
import { buildMessageId, nowTimeLabel } from "../core/utils";

const commandShortcuts = [
  "recap @thread",
  "draft reply to @contact",
  "prep @event",
  "draft from @message",
  "what changed since yesterday",
  "extract commitments",
];

const seedMessages: ChatMessage[] = [
  {
    id: "m1",
    role: "assistant",
    content: "Ready. Run a command, add @references, and I will keep it focused.",
    timestamp: "08:40",
  },
];

type DebugEvent = {
  ts: string;
  relMs: number;
  type: string;
  detail: string;
};

type DebugMetrics = {
  ttfvMs: number | null;
  ttftMs: number | null;
  totalMs: number | null;
};

export default function ChatPage() {
  const { userId } = usePlayground();
  const [messages, setMessages] = useState<ChatMessage[]>(seedMessages);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>("");
  const [mentions, setMentions] = useState<MentionChip[]>([]);
  const [mentionActive, setMentionActive] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionSuggestions, setMentionSuggestions] = useState<MentionSuggestion[]>([]);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0);
  const [mentionLoading, setMentionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugEvents, setDebugEvents] = useState<DebugEvent[]>([]);
  const [debugMetrics, setDebugMetrics] = useState<DebugMetrics>({
    ttfvMs: null,
    ttftMs: null,
    totalMs: null,
  });

  useEffect(() => {
    setSessionId("");
    setMessages(seedMessages);
  }, [userId]);

  async function ensureSession(): Promise<string> {
    if (sessionId) {
      return sessionId;
    }
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      throw new Error("Set a user profile first.");
    }
    const created = await createChatSession(scopedUserId, "command");
    const nextId = created.id;
    setSessionId(nextId);
    return nextId;
  }

  function nowMs(): number {
    if (typeof performance !== "undefined" && typeof performance.now === "function") {
      return performance.now();
    }
    return Date.now();
  }

  async function fetchSuggestions(query: string) {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      setMentionSuggestions([]);
      return;
    }
    setMentionLoading(true);
    try {
      const data = await fetchMentionSuggestions(scopedUserId, query);
      setMentionSuggestions(data as MentionSuggestion[]);
      setActiveSuggestionIndex(0);
    } catch {
      setMentionSuggestions([]);
    } finally {
      setMentionLoading(false);
    }
  }

  useEffect(() => {
    const scopedUserId = userId.trim();
    if (!scopedUserId || sessionId) {
      return;
    }
    void ensureSession().catch(() => {
      // session will be lazily created on first send
    });
  }, [userId, sessionId]);

  function onComposerChange(next: string) {
    setInput(next);
    const mentionMatch = next.match(/(?:^|\s)@([^\s@]*)$/);
    if (!mentionMatch) {
      setMentionActive(false);
      setMentionQuery("");
      setMentionSuggestions([]);
      return;
    }
    setMentionActive(true);
    const query = mentionMatch[1] || "";
    setMentionQuery(query);
    void fetchSuggestions(query);
  }

  function selectMention(suggestion: MentionSuggestion) {
    const mentionMatch = input.match(/(?:^|\s)@([^\s@]*)$/);
    if (!mentionMatch || mentionMatch.index === undefined) {
      return;
    }
    const fullMatch = mentionMatch[0];
    const refStart = mentionMatch.index + fullMatch.lastIndexOf("@");
    const displayLabel = suggestion.display_label || suggestion.label;
    const next = `${input.slice(0, refStart)}@${displayLabel} `;
    setInput(next);
    setMentionActive(false);
    setMentionQuery("");
    setMentionSuggestions([]);
    setActiveSuggestionIndex(0);

    setMentions((prev) => {
      const key = `${suggestion.kind}:${suggestion.ref.toLowerCase()}`;
      if (prev.some((m) => `${m.kind}:${m.ref.toLowerCase()}` === key)) {
        return prev;
      }
      return [...prev, { kind: suggestion.kind, ref: suggestion.ref, label: displayLabel }];
    });
  }

  function removeMention(target: MentionChip) {
    setMentions((prev) => prev.filter((m) => !(m.kind === target.kind && m.ref === target.ref)));
  }

  async function sendMessage() {
    if (isSending) {
      return;
    }
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      setError("Set a user profile first.");
      return;
    }
    if (!input.trim()) {
      return;
    }

    const messageText = input.trim();
    const outboundMentions = mentions.map((m) => ({ kind: m.kind, ref: m.ref, label: m.label }));
    const assistantId = buildMessageId();
    const startedAt = nowTimeLabel();
    const turnStartMs = nowMs();
    const appendDebug = (type: string, detail: string, atMs?: number) => {
      const stamp = atMs ?? nowMs();
      const relMs = Math.max(0, Math.round(stamp - turnStartMs));
      const ts = new Date().toISOString();
      setDebugEvents((prev) => [...prev.slice(-120), { ts, relMs, type, detail }]);
    };
    const stageCopy: Record<string, string> = {
      thinking: "Thinking...",
      checking_context: "Checking references...",
      planning: "Planning...",
      running_tools: "Working on it...",
      composing: "Finalizing...",
      drafting: "Drafting...",
    };

    let tokenSeen = false;
    let turnEnded = false;

    setDebugEvents([]);
    setDebugMetrics({ ttfvMs: null, ttftMs: null, totalMs: null });
    appendDebug("send", "User message submitted");

    const userMessage: ChatMessage = {
      id: buildMessageId(),
      role: "user",
      content: messageText,
      timestamp: nowTimeLabel(),
    };
    const assistantPlaceholder: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "Thinking...",
      timestamp: startedAt,
      gate: null,
    };
    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    const ttfvMs = Math.max(0, Math.round(nowMs() - turnStartMs));
    setDebugMetrics((prev) => ({ ...prev, ttfvMs }));
    appendDebug("ui", `Assistant visible (${ttfvMs}ms)`);
    setError(null);
    setInput("");
    setMentions([]);
    setMentionActive(false);
    setMentionQuery("");
    setMentionSuggestions([]);
    setIsSending(true);

    try {
      const activeSessionId = await ensureSession();
      appendDebug("session", `Using session ${activeSessionId}`);
      const updateAssistant = (mutator: (current: ChatMessage) => ChatMessage) => {
        setMessages((prev) =>
          prev.map((msg) => (msg.id === assistantId ? mutator(msg) : msg)),
        );
      };

      await streamChatMessage({
        user_id: scopedUserId,
        session_id: activeSessionId,
        content: messageText,
        mentions: outboundMentions,
        onEvent: (event) => {
          if (event.type === "state") {
            if (tokenSeen) return;
            const stage = String(event.payload?.stage || "");
            const next = stageCopy[stage] || "Thinking...";
            updateAssistant((current) => ({ ...current, content: next }));
            appendDebug("state", stage || "unknown");
            return;
          }
          if (event.type === "token") {
            const chunk = String(event.payload?.text || "");
            if (!chunk) return;
            if (!tokenSeen) {
              const ttftMs = Math.max(0, Math.round(nowMs() - turnStartMs));
              setDebugMetrics((prev) => ({ ...prev, ttftMs }));
              appendDebug("token", `First token (${ttftMs}ms)`);
            }
            tokenSeen = true;
            updateAssistant((current) => {
              const baseline = current.content === "Thinking..." || current.content.endsWith("...") ? "" : current.content;
              return { ...current, content: `${baseline}${chunk}` };
            });
            return;
          }
          if (event.type === "complete") {
            const finalResponse = String(event.payload?.response || "").trim();
            if (finalResponse) {
              updateAssistant((current) => ({ ...current, content: finalResponse }));
            }
            const totalMs = Math.max(0, Math.round(nowMs() - turnStartMs));
            setDebugMetrics((prev) => ({ ...prev, totalMs }));
            appendDebug("complete", `Stream complete (${totalMs}ms)`);
            turnEnded = true;
            return;
          }
          if (event.type === "error") {
            const message = String(event.payload?.message || "I couldn't complete that right now. Please try again.");
            updateAssistant((current) => ({ ...current, content: message }));
            const totalMs = Math.max(0, Math.round(nowMs() - turnStartMs));
            setDebugMetrics((prev) => ({ ...prev, totalMs }));
            appendDebug("error", message);
            turnEnded = true;
          }
        },
      });
      if (!turnEnded) {
        const totalMs = Math.max(0, Math.round(nowMs() - turnStartMs));
        setDebugMetrics((prev) => ({ ...prev, totalMs }));
        appendDebug("complete", `Stream closed (${totalMs}ms)`);
      }
    } catch {
      appendDebug("fallback", "SSE unavailable, switching to sync endpoint");
      // Fallback to non-stream endpoint if SSE is unavailable.
      try {
        const activeSessionId = sessionId || (await ensureSession());
        const data = await sendChatMessageV1({
          user_id: scopedUserId,
          session_id: activeSessionId,
          content: messageText,
          mentions: outboundMentions,
        });
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? {
                ...msg,
                content: data.response || "Ready for your next command.",
              }
              : msg,
          ),
        );
        const totalMs = Math.max(0, Math.round(nowMs() - turnStartMs));
        setDebugMetrics((prev) => ({ ...prev, totalMs }));
        appendDebug("complete", `Sync fallback complete (${totalMs}ms)`);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Chat request failed.";
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? {
                ...msg,
                content: "I couldn't complete that right now. Please try again.",
              }
              : msg,
          ),
        );
        setError(message);
        const totalMs = Math.max(0, Math.round(nowMs() - turnStartMs));
        setDebugMetrics((prev) => ({ ...prev, totalMs }));
        appendDebug("error", message);
      }
    } finally {
      setIsSending(false);
    }
  }

  useEffect(() => {
    if (!mentionActive) {
      setMentionSuggestions([]);
    }
  }, [mentionActive]);

  return (
    <div className="chat-panel">
      <div className="command-header">
        <p className="eyebrow">Teeks Command Surface</p>
        <h2 className="command-title">The fastest way to think with Teeks</h2>
        <p className="command-subtitle">Type intent. Add @references. Get focused output.</p>
      </div>

      <div className="command-feed">
        {messages.map((message) => (
          <div key={message.id} className={message.role === "assistant" ? "command-item result" : "command-item input"}>
            <div className="command-meta">
              <span>{message.role === "assistant" ? "Teeks" : "You"}</span>
              <span>{message.timestamp}</span>
            </div>
            <div className="command-content">{message.content}</div>
            {message.gate ? <div className="command-gate">Context: {message.gate.context_level}</div> : null}
          </div>
        ))}
      </div>

      <div className="command-actions">
        <div className="command-shortcuts">
          {commandShortcuts.map((command) => (
            <button key={command} type="button" className="chip ghost" onClick={() => onComposerChange(command)}>
              {command}
            </button>
          ))}
        </div>

        <div className="command-composer">
          {error ? <div className="notice">{error}</div> : null}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div className="notice">
              Stream debug: TTFV {debugMetrics.ttfvMs ?? "-"}ms · TTFT {debugMetrics.ttftMs ?? "-"}ms · Total {debugMetrics.totalMs ?? "-"}ms
            </div>
            <button type="button" className="chip ghost" onClick={() => setDebugOpen((v) => !v)}>
              {debugOpen ? "Hide debug" : "Show debug"}
            </button>
          </div>
          {debugOpen ? (
            <div
              style={{
                maxHeight: 160,
                overflowY: "auto",
                border: "1px solid rgba(255,255,255,0.14)",
                borderRadius: 12,
                padding: 10,
                marginBottom: 10,
                background: "rgba(255,255,255,0.03)",
                display: "grid",
                gap: 6,
              }}
            >
              {debugEvents.length ? (
                debugEvents.map((evt, idx) => (
                  <div key={`${evt.ts}-${idx}`} className="notice">
                    +{evt.relMs}ms · {evt.type}: {evt.detail}
                  </div>
                ))
              ) : (
                <div className="notice">No events yet.</div>
              )}
            </div>
          ) : null}
          {mentions.length ? (
            <div className="mention-chip-row">
              {mentions.map((mention) => (
                <button key={`${mention.kind}:${mention.ref}`} type="button" className="chip mention-chip" onClick={() => removeMention(mention)}>
                  @{mention.label} ({mention.kind})
                </button>
              ))}
            </div>
          ) : null}

          <div className="command-input-wrap">
            <span className="command-prompt">&gt;</span>
            <textarea
              className="textarea command-input"
              placeholder="Type a command or question..."
              value={input}
              onChange={(e) => onComposerChange(e.target.value)}
              onKeyDown={(e) => {
                if (mentionActive && mentionSuggestions.length > 0) {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActiveSuggestionIndex((prev) => (prev + 1) % mentionSuggestions.length);
                    return;
                  }
                  if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActiveSuggestionIndex((prev) => (prev - 1 + mentionSuggestions.length) % mentionSuggestions.length);
                    return;
                  }
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    selectMention(mentionSuggestions[activeSuggestionIndex]);
                    return;
                  }
                  if (e.key === "Tab") {
                    e.preventDefault();
                    selectMention(mentionSuggestions[activeSuggestionIndex]);
                    return;
                  }
                }
                if (e.key === "Escape") {
                  setMentionActive(false);
                  setMentionQuery("");
                  setMentionSuggestions([]);
                  return;
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendMessage();
                }
              }}
            />
          </div>

          {mentionActive && (mentionLoading || mentionSuggestions.length > 0 || !mentionQuery) ? (
            <div className="mention-suggestions">
              {mentionLoading ? (
                <div className="notice">Finding references...</div>
              ) : (
                mentionSuggestions.length ? (
                  mentionSuggestions.map((suggestion, index) => (
                    <button
                      key={`${suggestion.kind}:${suggestion.ref}`}
                      type="button"
                      className={`mention-option ${index === activeSuggestionIndex ? "active" : ""}`}
                      onClick={() => selectMention(suggestion)}
                    >
                      <div className="mention-option-main">
                        <span>@{suggestion.display_label || suggestion.label}</span>
                        <span className="notice">{suggestion.kind}</span>
                      </div>
                      {suggestion.subtitle ? <div className="mention-option-subtitle">{suggestion.subtitle}</div> : null}
                    </button>
                  ))
                ) : (
                  <div className="notice">No matches yet. Keep typing.</div>
                )
              )}
            </div>
          ) : null}

          <div className="composer-footer">
            <span className="notice">Enter to run. Shift+Enter for newline.</span>
            <button className="button" disabled={isSending} onClick={() => void sendMessage()}>
              {isSending ? "Running..." : "Run"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
