import { api } from "./api";

export type VaultNoteType = "person" | "project" | "meeting" | "decision" | "commitment";

export interface VaultNote {
  id: number;
  user_id: string;
  slug: string;
  note_type: VaultNoteType;
  title: string;
  frontmatter: Record<string, unknown>;
  body: string;
  canonical_email?: string | null;
  aliases: string[];
  source: string;
  confidence: number;
  status: string;
  pinned: boolean;
  created_at: string;
  updated_at: string;
  last_referenced_at?: string | null;
}

export type DiaryEntryType = "decision" | "commitment" | "preferences" | "insight" | "relationships";
export type DiaryEntityType = "assistant" | "executive" | "contact" | "thread" | "event";
export type DiaryImportance = "low" | "normal" | "high";
export type DiaryStatus = "active" | "resolved" | "stale" | "archived";

export interface DiaryEntryLink {
  entity_type: string;
  entity_id: string;
  display_name: string;
}

export interface DiaryContextEntry {
  id: number;
  user_id: string;
  type: DiaryEntryType;
  content: string;
  entity_type: DiaryEntityType;
  entity_id?: string | null;
  created_by: "Teeks" | "You";
  importance_level: DiaryImportance;
  status: DiaryStatus;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
  links: DiaryEntryLink[];
}

export interface DiaryContact {
  id: number;
  user_id: string;
  name: string;
  email?: string | null;
  role?: string | null;
  organization?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DiaryEntityReference {
  id: number;
  user_id: string;
  entity_type: "thread" | "event";
  display_name: string;
  ref: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export async function fetchVaultNotes(params?: {
  note_type?: VaultNoteType;
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<{ notes: VaultNote[]; total: number }> {
  const response = await api.get("/vault/notes", { params });
  return response.data;
}

export async function createVaultNote(payload: {
  note_type: VaultNoteType;
  title: string;
  body?: string;
  frontmatter?: Record<string, unknown>;
  canonical_email?: string;
}): Promise<VaultNote> {
  const response = await api.post("/vault/notes", payload);
  return response.data;
}

export async function updateVaultNote(
  noteId: number,
  payload: Partial<Pick<VaultNote, "title" | "body" | "frontmatter" | "pinned" | "status">>
): Promise<VaultNote> {
  const response = await api.put(`/vault/notes/${noteId}`, payload);
  return response.data;
}

export async function fetchDiaryContextEntries(params?: {
  type?: DiaryEntryType;
  entity_type?: DiaryEntityType;
  entity_id?: string;
}): Promise<DiaryContextEntry[]> {
  const response = await api.get("/vault/diary/context-entries", { params });
  return response.data;
}

export async function createDiaryContextEntry(payload: {
  type: DiaryEntryType;
  content: string;
  entity_type?: DiaryEntityType;
  entity_id?: string | null;
  created_by?: "Teeks" | "You";
  importance_level?: DiaryImportance;
  status?: DiaryStatus;
  expires_at?: string | null;
  links?: DiaryEntryLink[];
}): Promise<DiaryContextEntry> {
  const response = await api.post("/vault/diary/context-entries", payload);
  return response.data;
}

export async function updateDiaryContextEntry(
  id: number,
  payload: Partial<Pick<DiaryContextEntry, "content" | "importance_level" | "status" | "expires_at">>
): Promise<DiaryContextEntry> {
  const response = await api.put(`/vault/diary/context-entries/${id}`, payload);
  return response.data;
}

export async function deleteDiaryContextEntry(id: number): Promise<{ deleted: boolean; id: number }> {
  const response = await api.delete(`/vault/diary/context-entries/${id}`);
  return response.data;
}

export async function fetchDiaryContacts(q?: string): Promise<DiaryContact[]> {
  const response = await api.get("/vault/diary/contacts", { params: { q: q || undefined } });
  return response.data;
}

export async function createDiaryContact(payload: {
  name: string;
  email?: string | null;
  role?: string | null;
  organization?: string | null;
  notes?: string | null;
}): Promise<DiaryContact> {
  const response = await api.post("/vault/diary/contacts", payload);
  return response.data;
}

export async function updateDiaryContact(
  id: number,
  payload: Partial<Pick<DiaryContact, "name" | "email" | "role" | "organization" | "notes">>
): Promise<DiaryContact> {
  const response = await api.put(`/vault/diary/contacts/${id}`, payload);
  return response.data;
}

export async function deleteDiaryContact(id: number): Promise<{ deleted: boolean; id: number }> {
  const response = await api.delete(`/vault/diary/contacts/${id}`);
  return response.data;
}

export async function fetchDiaryEntityReferences(params?: {
  entity_type?: "thread" | "event";
  q?: string;
}): Promise<DiaryEntityReference[]> {
  const response = await api.get("/vault/diary/entity-references", { params });
  return response.data;
}

export async function createDiaryEntityReference(payload: {
  entity_type: "thread" | "event";
  display_name: string;
  ref: string;
  notes?: string | null;
}): Promise<DiaryEntityReference> {
  const response = await api.post("/vault/diary/entity-references", payload);
  return response.data;
}

export async function updateDiaryEntityReference(
  id: number,
  payload: Partial<Pick<DiaryEntityReference, "display_name" | "ref" | "notes">>
): Promise<DiaryEntityReference> {
  const response = await api.put(`/vault/diary/entity-references/${id}`, payload);
  return response.data;
}

export async function deleteDiaryEntityReference(id: number): Promise<{ deleted: boolean; id: number }> {
  const response = await api.delete(`/vault/diary/entity-references/${id}`);
  return response.data;
}
