"use client";

import { useState } from "react";
import { usePlayground, type ContactFormState } from "../core/PlaygroundProvider";

export default function ContactsPage() {
  const { contacts, createContact, deleteContact, error } = usePlayground();
  const [contactForm, setContactForm] = useState<ContactFormState>({
    name: "",
    email: "",
    role: "",
    organization: "",
    notes: "",
  });

  return (
    <div className="page-panel">
      <section className="memory-block">
        <h2 className="section-title">Contacts</h2>
        <div className="entry-form-card">
          {error ? <div className="notice">{error}</div> : null}
          <div className="form">
            <input className="input" placeholder="Name" value={contactForm.name} onChange={(e) => setContactForm((prev) => ({ ...prev, name: e.target.value }))} />
            <input className="input" placeholder="Email (optional)" value={contactForm.email} onChange={(e) => setContactForm((prev) => ({ ...prev, email: e.target.value }))} />
            <input className="input" placeholder="Role (optional)" value={contactForm.role} onChange={(e) => setContactForm((prev) => ({ ...prev, role: e.target.value }))} />
            <input className="input" placeholder="Organization (optional)" value={contactForm.organization} onChange={(e) => setContactForm((prev) => ({ ...prev, organization: e.target.value }))} />
          </div>
          <textarea className="textarea" placeholder="Notes (optional)" value={contactForm.notes} onChange={(e) => setContactForm((prev) => ({ ...prev, notes: e.target.value }))} />
          <button
            className="button"
            onClick={async () => {
              await createContact(contactForm);
              setContactForm({ name: "", email: "", role: "", organization: "", notes: "" });
            }}
          >
            Save contact
          </button>
        </div>
        <div className="list">
          {contacts.map((contact) => (
            <div key={contact.id} className="entry">
              <div className="entry-meta">{contact.email || "No email"}</div>
              <div><strong>{contact.name}</strong></div>
              <div className="entry-meta">{contact.role || ""} {contact.organization ? `- ${contact.organization}` : ""}</div>
              <div className="row">
                <button className="button secondary" onClick={() => void deleteContact(contact.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
