"use client";

import { useMemo, useState } from "react";
import { usePlayground, type EntryFormState } from "../core/PlaygroundProvider";
import type { ContextEntry, ContextEntryType, ContextEntityType } from "../core/types";

const typeLabels: Record<ContextEntryType, string> = {
  decision: "Decisions",
  commitment: "Commitments",
  preferences: "Preferences",
  insight: "Risks",
  relationships: "Relationships",
};

export default function HomePage() {
  const { entries, contacts, entityRefs, createEntry } = usePlayground();

  const [entryForm, setEntryForm] = useState<EntryFormState>({
    type: "decision",
    content: "",
    entity_type: "executive",
    entity_id: "",
    importance_level: "normal",
    status: "active",
    expires_at: "",
  });

  const groupedEntries = useMemo(() => {
    const buckets: Record<string, ContextEntry[]> = {};
    entries.forEach((entry) => {
      const label = typeLabels[entry.type];
      if (!buckets[label]) {
        buckets[label] = [];
      }
      buckets[label].push(entry);
    });
    return buckets;
  }, [entries]);

  const linkedEntityOptions = useMemo(() => {
    if (entryForm.entity_type === "contact") {
      return contacts.map((c) => ({
        value: c.email,
        label: `${c.name} (${c.email})`,
      }));
    }
    if (entryForm.entity_type === "thread" || entryForm.entity_type === "event" || entryForm.entity_type === "message") {
      return entityRefs
        .filter((e) => e.entity_type === entryForm.entity_type)
        .map((e) => ({ value: e.ref, label: e.display_name }));
    }
    return [];
  }, [entryForm.entity_type, contacts, entityRefs]);

  return (
    <div className="page-panel">
      <section className="memory-block">
        <h2 className="section-title">Today</h2>
        <div className="memory-grid">
          {Object.entries(typeLabels).map(([typeKey, label]) => {
            const items = groupedEntries[label] || [];
            return (
              <div key={typeKey} className="memory-card">
                <div className="memory-card-header">
                  <strong>{label}</strong>
                  <span className="entry-meta">{items.length}</span>
                </div>
                <div className="list">
                  {items.length === 0 ? (
                    <div className="notice">No entries yet.</div>
                  ) : (
                    items.slice(0, 2).map((item) => (
                      <div key={item.id} className="entry">
                        <div className="entry-meta">{item.importance_level.toUpperCase()}</div>
                        <div>{item.content}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="memory-block">
        <h2 className="section-title">Quick capture</h2>
        <div className="entry-form-card">
          <textarea
            className="textarea"
            placeholder="Write what Teeks should remember..."
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
              onChange={(e) => setEntryForm((prev) => ({ ...prev, entity_type: e.target.value as ContextEntityType, entity_id: "" }))}
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
              onChange={(e) => setEntryForm((prev) => ({ ...prev, importance_level: e.target.value as ContextEntry["importance_level"] }))}
            >
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>
            <select
              className="select"
              value={entryForm.status}
              onChange={(e) => setEntryForm((prev) => ({ ...prev, status: e.target.value as ContextEntry["status"] }))}
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
            Save entry
          </button>
        </div>
      </section>
    </div>
  );
}
