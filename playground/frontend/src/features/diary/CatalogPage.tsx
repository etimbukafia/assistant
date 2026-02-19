"use client";

import { useState } from "react";
import { usePlayground } from "../core/PlaygroundProvider";
import type { EntityReferenceType } from "../core/types";

export default function CatalogPage() {
  const { createEntityReference } = usePlayground();
  const [entityForm, setEntityForm] = useState({
    entity_type: "thread" as EntityReferenceType,
    display_name: "",
    ref: "",
    notes: "",
  });

  return (
    <div className="page-panel">
      <section className="memory-block">
        <h2 className="section-title">Linked References</h2>
        <div className="notice">Add only. Existing references are intentionally hidden.</div>
        <div className="entry-form-card">
          <div className="form">
            <select
              className="select"
              value={entityForm.entity_type}
              onChange={(e) =>
                setEntityForm((prev) => ({
                  ...prev,
                  entity_type: e.target.value as EntityReferenceType,
                }))
              }
            >
              <option value="thread">Thread</option>
              <option value="event">Event</option>
              <option value="message">Message</option>
            </select>
            <input
              className="input"
              placeholder="Display name"
              value={entityForm.display_name}
              onChange={(e) => setEntityForm((prev) => ({ ...prev, display_name: e.target.value }))}
            />
            <input
              className="input"
              placeholder="Canonical reference"
              value={entityForm.ref}
              onChange={(e) => setEntityForm((prev) => ({ ...prev, ref: e.target.value }))}
            />
          </div>
          <textarea
            className="textarea"
            placeholder="Notes (optional)"
            value={entityForm.notes}
            onChange={(e) => setEntityForm((prev) => ({ ...prev, notes: e.target.value }))}
          />
          <button
            className="button"
            onClick={async () => {
              await createEntityReference(entityForm);
              setEntityForm({
                entity_type: "thread",
                display_name: "",
                ref: "",
                notes: "",
              });
            }}
          >
            Save reference
          </button>
        </div>
      </section>
    </div>
  );
}
