"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  createContact,
  createContextEntry,
  createEntityReference,
  deleteContact,
  deleteContextEntry,
  deleteEntityReference,
  fetchDiaryData,
  updateContextEntry,
} from "./api";
import type {
  CalendarEvent,
  Contact,
  ContextEntry,
  ContextEntryType,
  ContextEntityType,
  EntityReference,
  EntityReferenceType,
  InboxThread,
} from "./types";

const DEFAULT_USER_ID = "ea_demo";

export type EntryFormState = {
  type: ContextEntryType;
  content: string;
  entity_type: ContextEntityType;
  entity_id: string;
  importance_level: ContextEntry["importance_level"];
  status: ContextEntry["status"];
  expires_at: string;
};

export type ContactFormState = {
  name: string;
  email: string;
  role: string;
  organization: string;
  notes: string;
};

export type EntityFormState = {
  entity_type: EntityReferenceType;
  display_name: string;
  ref: string;
  notes: string;
};

export type PlaygroundContextValue = {
  userId: string;
  setUserId: (value: string) => void;
  entries: ContextEntry[];
  contacts: Contact[];
  entityRefs: EntityReference[];
  threads: InboxThread[];
  events: CalendarEvent[];
  loading: boolean;
  error: string | null;
  notice: string | null;
  setNotice: (message: string | null) => void;
  reloadAll: () => Promise<void>;
  createEntry: (payload: EntryFormState) => Promise<void>;
  updateEntry: (entryId: number, payload: {
    content: string;
    importance_level: ContextEntry["importance_level"];
    status?: ContextEntry["status"];
    expires_at?: string | null;
  }) => Promise<void>;
  deleteEntry: (entryId: number) => Promise<void>;
  createContact: (payload: ContactFormState) => Promise<void>;
  deleteContact: (contactId: number) => Promise<void>;
  createEntityReference: (payload: EntityFormState) => Promise<void>;
  deleteEntityReference: (entityId: number) => Promise<void>;
};

const PlaygroundContext = createContext<PlaygroundContextValue | null>(null);

export function PlaygroundProvider({ children }: { children: React.ReactNode }) {
  const [userId, setUserIdState] = useState(DEFAULT_USER_ID);
  const [entries, setEntries] = useState<ContextEntry[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [entityRefs, setEntityRefs] = useState<EntityReference[]>([]);
  const [threads, setThreads] = useState<InboxThread[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem("playground_user_id");
    if (stored && stored.trim()) {
      setUserIdState(stored.trim());
    }
  }, []);

  useEffect(() => {
    if (userId.trim()) {
      window.localStorage.setItem("playground_user_id", userId.trim());
    }
  }, [userId]);

  const reloadAll = async () => {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDiaryData(scopedUserId);
      setEntries(data.entries);
      setContacts(data.contacts);
      setEntityRefs(data.entities);
      setThreads(data.threads);
      setEvents(data.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error while loading diary");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reloadAll();
  }, [userId]);

  const setUserId = (value: string) => {
    setUserIdState(value);
  };

  const setNoticeMessage = (message: string | null) => {
    setNotice(message);
    if (message) {
      window.setTimeout(() => setNotice(null), 2400);
    }
  };

  const createEntryHandler = async (payload: EntryFormState) => {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      setError("Set a user profile first.");
      return;
    }
    if (!payload.content.trim()) {
      setError("Write what you want Teeks to remember.");
      return;
    }
    const needsLink = payload.entity_type !== "executive" && payload.entity_type !== "assistant";
    const entityId = payload.entity_id.trim();
    if (needsLink && !entityId) {
      setError("Select a linked contact, thread, message, or event.");
      return;
    }
    setError(null);
    let expiresAt = payload.expires_at.trim();
    if (expiresAt && !expiresAt.includes("T")) {
      expiresAt = `${expiresAt}T23:59:59Z`;
    }
    await createContextEntry(scopedUserId, {
      type: payload.type,
      content: payload.content.trim(),
      entity_type: payload.entity_type,
      entity_id: needsLink ? entityId : null,
      importance_level: payload.importance_level,
      status: payload.status,
      expires_at: expiresAt || null,
    });
    await reloadAll();
    setNoticeMessage("Entry saved.");
  };

  const updateEntryHandler = async (entryId: number, payload: {
    content: string;
    importance_level: ContextEntry["importance_level"];
    status?: ContextEntry["status"];
    expires_at?: string | null;
  }) => {
    if (!payload.content.trim()) {
      setError("Entry content cannot be empty.");
      return;
    }
    setError(null);
    await updateContextEntry(entryId, {
      content: payload.content.trim(),
      importance_level: payload.importance_level,
      status: payload.status,
      expires_at: payload.expires_at,
    });
    await reloadAll();
    setNoticeMessage("Updated entry.");
  };

  const deleteEntryHandler = async (entryId: number) => {
    setError(null);
    await deleteContextEntry(entryId);
    await reloadAll();
    setNoticeMessage("Deleted entry.");
  };

  const createContactHandler = async (payload: ContactFormState) => {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      setError("Set a user profile first.");
      return;
    }
    if (!payload.name.trim()) {
      setError("Contact name is required.");
      return;
    }
    setError(null);
    try {
      await createContact(scopedUserId, payload);
      await reloadAll();
      setNoticeMessage("Saved contact.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save contact.");
    }
  };

  const deleteContactHandler = async (contactId: number) => {
    setError(null);
    await deleteContact(contactId);
    await reloadAll();
    setNoticeMessage("Deleted contact.");
  };

  const createEntityReferenceHandler = async (payload: EntityFormState) => {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      setError("Set a user profile first.");
      return;
    }
    if (!payload.display_name.trim() || !payload.ref.trim()) {
      setError("Entity name and reference are required.");
      return;
    }
    setError(null);
    await createEntityReference(scopedUserId, payload);
    await reloadAll();
    setNoticeMessage("Saved reference.");
  };

  const deleteEntityReferenceHandler = async (entityId: number) => {
    setError(null);
    await deleteEntityReference(entityId);
    await reloadAll();
    setNoticeMessage("Deleted reference.");
  };

  const value = useMemo<PlaygroundContextValue>(
    () => ({
      userId,
      setUserId,
      entries,
      contacts,
      entityRefs,
      threads,
      events,
      loading,
      error,
      notice,
      setNotice: setNoticeMessage,
      reloadAll,
      createEntry: createEntryHandler,
      updateEntry: updateEntryHandler,
      deleteEntry: deleteEntryHandler,
      createContact: createContactHandler,
      deleteContact: deleteContactHandler,
      createEntityReference: createEntityReferenceHandler,
      deleteEntityReference: deleteEntityReferenceHandler,
    }),
    [
      userId,
      entries,
      contacts,
      entityRefs,
      threads,
      events,
      loading,
      error,
      notice,
    ],
  );

  return <PlaygroundContext.Provider value={value}>{children}</PlaygroundContext.Provider>;
}

export function usePlayground() {
  const ctx = useContext(PlaygroundContext);
  if (!ctx) {
    throw new Error("usePlayground must be used within PlaygroundProvider");
  }
  return ctx;
}
