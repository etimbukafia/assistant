"use client";

import { useEffect, useMemo, useState } from "react";
import { usePlayground } from "../core/PlaygroundProvider";
import { draftEmail, fetchThreadIntelligence, fetchThreadMessages, updateThreadStatus } from "../core/api";
import type { EmailDraftResult, InboxMessage, InboxThread, ThreadIntelligenceResult } from "../core/types";

export default function InboxPage() {
  const { userId, threads, reloadAll } = usePlayground();
  const [inboxView, setInboxView] = useState<"inbox" | "archived">("inbox");
  const [selectedThreadId, setSelectedThreadId] = useState<string>("");
  const [threadMessages, setThreadMessages] = useState<InboxMessage[]>([]);
  const [threadIntelligence, setThreadIntelligence] = useState<ThreadIntelligenceResult | null>(null);
  const [draftResult, setDraftResult] = useState<EmailDraftResult | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const visibleThreads = useMemo(
    () => threads.filter((t) => (inboxView === "archived" ? t.status === "closed" : t.status !== "closed")),
    [threads, inboxView],
  );

  const selectedThread = useMemo(
    () => threads.find((t) => t.thread_id === selectedThreadId) || null,
    [threads, selectedThreadId],
  );

  useEffect(() => {
    if (!visibleThreads.length) {
      setSelectedThreadId("");
      setThreadMessages([]);
      setThreadIntelligence(null);
      return;
    }
    if (!visibleThreads.some((thread) => thread.thread_id === selectedThreadId)) {
      setSelectedThreadId(visibleThreads[0].thread_id);
    }
  }, [visibleThreads, selectedThreadId]);

  useEffect(() => {
    const scopedUserId = userId.trim();
    if (!selectedThreadId || !scopedUserId) {
      setThreadMessages([]);
      setThreadIntelligence(null);
      return;
    }

    void (async () => {
      const [messages, intelligence] = await Promise.all([
        fetchThreadMessages(scopedUserId, selectedThreadId),
        fetchThreadIntelligence(scopedUserId, selectedThreadId),
      ]);
      setThreadMessages(messages);
      setThreadIntelligence(intelligence);
    })();
  }, [selectedThreadId, userId]);

  async function handleDraftFromThread(threadItem: InboxThread) {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      return;
    }
    setActionLoading(true);
    try {
      const data = await draftEmail(scopedUserId, {
        subject: threadItem.subject,
        intent: "follow up with clear next step",
        thread_id: threadItem.thread_id,
      });
      setDraftResult(data);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDraftFromMessage(messageItem: InboxMessage) {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      return;
    }
    setActionLoading(true);
    try {
      const data = await draftEmail(scopedUserId, {
        subject: messageItem.subject,
        intent: "reply with crisp status and next action",
        thread_id: messageItem.thread_id,
        message_id: messageItem.message_id,
      });
      setDraftResult(data);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleUpdateStatus(threadId: string, status: "open" | "waiting" | "closed") {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      return;
    }
    await updateThreadStatus(scopedUserId, threadId, status);
    await reloadAll();
  }

  return (
    <div className="page-panel">
      <section className="memory-block">
        <div className="section-toolbar">
          <h2 className="section-title">Inbox</h2>
          <div className="segmented-control">
            <button
              className={`segmented-button ${inboxView === "inbox" ? "active" : ""}`}
              onClick={() => setInboxView("inbox")}
            >
              Inbox
            </button>
            <button
              className={`segmented-button ${inboxView === "archived" ? "active" : ""}`}
              onClick={() => setInboxView("archived")}
            >
              Archive
            </button>
          </div>
        </div>

        <div className="inbox-layout">
          <div className="inbox-list">
            {visibleThreads.length === 0 ? (
              <div className="entry">
                <div className="entry-meta">
                  {inboxView === "archived" ? "No archived threads yet." : "Inbox is clear."}
                </div>
              </div>
            ) : (
              visibleThreads.map((threadItem) => (
                <button
                  key={threadItem.thread_id}
                  type="button"
                  className={`entry thread-row ${selectedThreadId === threadItem.thread_id ? "is-selected" : ""}`}
                  onClick={() => {
                    setSelectedThreadId(threadItem.thread_id);
                    setDraftResult(null);
                  }}
                >
                  <div className="entry-meta">{threadItem.last_sender || "Unknown sender"} | {threadItem.status}</div>
                  <div><strong>{threadItem.subject}</strong></div>
                  <div className="entry-meta">{threadItem.snippet || "No preview available."}</div>
                  <div className="entry-meta">
                    {new Date(threadItem.last_received_at).toLocaleString()} | unread {threadItem.unread_count}
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="inbox-detail">
            {selectedThread ? (
              <>
                <div className="entry">
                  <div className="entry-meta">Thread</div>
                  <div><strong>{selectedThread.subject}</strong></div>
                  <div className="row">
                    <button className="button" onClick={() => void handleDraftFromThread(selectedThread)}>
                      {actionLoading ? "Drafting..." : "Draft reply"}
                    </button>
                    {selectedThread.status === "closed" ? (
                      <button className="button secondary" onClick={() => void handleUpdateStatus(selectedThread.thread_id, "open")}>
                        Reopen
                      </button>
                    ) : (
                      <button className="button secondary" onClick={() => void handleUpdateStatus(selectedThread.thread_id, "closed")}>
                        Archive
                      </button>
                    )}
                    {selectedThread.status !== "waiting" ? (
                      <button className="button secondary" onClick={() => void handleUpdateStatus(selectedThread.thread_id, "waiting")}>
                        Waiting
                      </button>
                    ) : null}
                  </div>
                </div>

                {threadIntelligence ? (
                  <div className="entry">
                    <div className="entry-meta">Thread intelligence</div>
                    <div>{threadIntelligence.summary}</div>
                    {threadIntelligence.action_points.length ? (
                      <div className="compact-list">
                        {threadIntelligence.action_points.slice(0, 3).map((point, idx) => (
                          <div key={`action-${idx}`}>- {point}</div>
                        ))}
                      </div>
                    ) : null}
                    {threadIntelligence.decisions.length ? (
                      <div className="compact-list">
                        <strong>Decisions</strong>
                        {threadIntelligence.decisions.slice(0, 2).map((item, idx) => (
                          <div key={`decision-${idx}`}>- {item}</div>
                        ))}
                      </div>
                    ) : null}
                    {threadIntelligence.commitments.length ? (
                      <div className="compact-list">
                        <strong>Commitments</strong>
                        {threadIntelligence.commitments.slice(0, 2).map((item, idx) => (
                          <div key={`commitment-${idx}`}>- {item}</div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                <div className="list">
                  {threadMessages.map((message) => (
                    <div key={message.message_id} className="entry">
                      <div className="entry-meta">{message.direction.toUpperCase()} | {message.sender}</div>
                      <div><strong>{message.subject}</strong></div>
                      <div>{message.body_preview}</div>
                      <div className="row">
                        <button className="button secondary" onClick={() => void handleDraftFromMessage(message)}>
                          Draft from message
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="entry">
                <div className="entry-meta">Select a thread to open detail.</div>
              </div>
            )}
          </div>
        </div>

        {draftResult ? (
          <div className="entry">
            <div className="entry-meta">Email draft | {draftResult.subject}</div>
            <pre className="draft-preview">{draftResult.body}</pre>
          </div>
        ) : null}
      </section>
    </div>
  );
}
