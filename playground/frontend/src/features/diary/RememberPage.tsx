"use client";

import { useMemo, useState } from "react";
import { usePlayground } from "../core/PlaygroundProvider";
import type { EntryFormState } from "../core/PlaygroundProvider";
import type { ContextEntityType, ContextEntryType } from "../core/types";

export default function RememberPage() {
  const { contacts, entityRefs, createEntry } = usePlayground();

  const [entryForm, setEntryForm] = useState<EntryFormState>({
    type: "decision",
    content: "",
    entity_type: "executive",
    entity_id: "",
    importance_level: "normal",
    status: "active",
    expires_at: "",
  });
  const linkedEntityOptions = useMemo(() => {
    if (entryForm.entity_type === "contact") {
      return contacts
        .filter((c) => !!c.email)
        .map((c) => ({
          value: c.email || "",
          label: `${c.name}${c.email ? ` (${c.email})` : ""}`,
        }));
    }
    if (entryForm.entity_type === "thread" || entryForm.entity_type === "event" || entryForm.entity_type === "message") {
      return entityRefs
        .filter((e) => e.entity_type === entryForm.entity_type)
        .map((e) => ({
          value: e.ref,
          label: e.display_name,
        }));
    }
    return [];
  }, [contacts, entityRefs, entryForm.entity_type]);

  return (
    <div className="page-panel">
      <section className="memory-block">
        <h2 className="section-title">Remember</h2>
        <div className="notice">Add only. Saved memories are intentionally hidden.</div>
        <div className="entry-form-card">
          <textarea
            className="textarea"
            placeholder="What should Teeks remember?"
            value={entryForm.content}
            onChange={(e) => setEntryForm((prev) => ({ ...prev, content: e.target.value }))}
          />
          <div className="form">
            <select
              className="select"
              value={entryForm.type}
              onChange={(e) => setEntryForm((prev) => ({ ...prev, type: e.target.value as ContextEntryType }))}
            >
              <option value="decision">Decision</option>
              <option value="commitment">Commitment</option>
              <option value="preferences">Preference</option>
              <option value="insight">Risk</option>
              <option value="relationships">Relationship</option>
            </select>
            <select
              className="select"
              value={entryForm.entity_type}
              onChange={(e) =>
                setEntryForm((prev) => ({
                  ...prev,
                  entity_type: e.target.value as ContextEntityType,
                  entity_id: "",
                }))
              }
            >
              <option value="executive">Executive</option>
              <option value="assistant">Assistant</option>
              <option value="contact">Contact</option>
              <option value="thread">Thread</option>
              <option value="event">Event</option>
              <option value="message">Message</option>
            </select>
            <select
              className="select"
              value={entryForm.importance_level}
              onChange={(e) =>
                setEntryForm((prev) => ({
                  ...prev,
                  importance_level: e.target.value as EntryFormState["importance_level"],
                }))
              }
            >
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>
            <select
              className="select"
              value={entryForm.status}
              onChange={(e) =>
                setEntryForm((prev) => ({
                  ...prev,
                  status: e.target.value as EntryFormState["status"],
                }))
              }
            >
              <option value="active">Active</option>
              <option value="resolved">Resolved</option>
              <option value="stale">Stale</option>
              <option value="archived">Archived</option>
            </select>
            {entryForm.entity_type !== "executive" && entryForm.entity_type !== "assistant" ? (
              <select
                className="select"
                value={entryForm.entity_id}
                onChange={(e) => setEntryForm((prev) => ({ ...prev, entity_id: e.target.value }))}
              >
                <option value="">Link to...</option>
                {linkedEntityOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : null}
          </div>
          <input
            className="input"
            type="date"
            placeholder="Expires (optional)"
            value={entryForm.expires_at}
            onChange={(e) => setEntryForm((prev) => ({ ...prev, expires_at: e.target.value }))}
          />
          <button
            className="button"
            onClick={async () => {
              await createEntry(entryForm);
              setEntryForm({
                type: "decision",
                content: "",
                entity_type: "executive",
                entity_id: "",
                importance_level: "normal",
                status: "active",
                expires_at: "",
              });
            }}
          >
            Save memory
          </button>
        </div>
      </section>
    </div>
  );
}
