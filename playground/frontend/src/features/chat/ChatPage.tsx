"use client";

import { useEffect, useState } from "react";
import { fetchMentionSuggestions, sendChatMessage } from "../core/api";
import { usePlayground } from "../core/PlaygroundProvider";
import type {
  ChatMessage,
  GateDecision,
  MentionChip,
  MentionSuggestion,
} from "../core/types";
import { buildMessageId, buildSessionId, nowTimeLabel } from "../core/utils";

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

export default function ChatPage() {
  const { userId } = usePlayground();
  const [messages, setMessages] = useState<ChatMessage[]>(seedMessages);
  const [input, setInput] = useState("");
  const [sessionId] = useState<string>(() => buildSessionId());
  const [gateSummary, setGateSummary] = useState<GateDecision | null>(null);
  const [mentions, setMentions] = useState<MentionChip[]>([]);
  const [mentionActive, setMentionActive] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionSuggestions, setMentionSuggestions] = useState<MentionSuggestion[]>([]);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0);
  const [mentionLoading, setMentionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

    const userMessage: ChatMessage = {
      id: buildMessageId(),
      role: "user",
      content: messageText,
      timestamp: nowTimeLabel(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setError(null);

    try {
      const data = await sendChatMessage({
        message: messageText,
        user_id: scopedUserId,
        session_id: sessionId,
        current_state: {},
        mentions: outboundMentions,
      });

      const assistantMessage: ChatMessage = {
        id: buildMessageId(),
        role: "assistant",
        content: data.reply || "Ready for your next command.",
        timestamp: nowTimeLabel(),
        gate: (data as { gate?: GateDecision }).gate || null,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setGateSummary((data as { gate?: GateDecision }).gate || null);
      setInput("");
      setMentions([]);
      setMentionActive(false);
      setMentionQuery("");
      setMentionSuggestions([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed.");
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
          {gateSummary ? <div className="notice">Last context level: {gateSummary.context_level}</div> : null}
          {error ? <div className="notice">{error}</div> : null}
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
            <button className="button" onClick={() => void sendMessage()}>Run</button>
          </div>
        </div>
      </div>
    </div>
  );
}
