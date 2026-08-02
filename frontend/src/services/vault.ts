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

export const CONTEXT_CAPTURE_MAX_CHARS = 2000;

export type DiaryEntryType = "decision" | "commitment" | "preference" | "risk" | "insight";
export type DiaryEntityType = "global" | "contact" | "thread" | "event" | "message" | "task";
export type DiaryCaptureScopeType = "global" | "contact" | "message" | "event" | "task";
export type DiaryStatus = "active" | "resolved" | "stale" | "archived" | "forgotten";

export interface DiaryEntryLink {
  entity_type: string;
  entity_id: string;
  display_name: string;
  source: "user" | "teeks";
}

export interface DiaryContextEntry {
  id: number;
  user_id: string;
  type: DiaryEntryType;
  content: string;
  raw_text?: string | null;
  entity_type: DiaryEntityType;
  entity_id?: string | null;
  linked_to?: string | null;
  created_by: "Teeks" | "You";
  status: DiaryStatus;
  classification_status: "pending" | "classified" | "user_corrected";
  classification_confidence?: number | null;
  user_corrected: boolean;
  scope_resolved?: boolean;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
  links: DiaryEntryLink[];
}

export type ContactCategory = "vip" | "colleague" | "external" | "vendor";

export interface DiaryContact {
  id: number;
  user_id: string;
  name: string;
  email?: string | null;
  role?: string | null;
  organization?: string | null;
  notes?: string | null;
  category?: ContactCategory | null;
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
  const response = await api.get("/context/captures", { params });
  return response.data;
}

export async function createDiaryContextEntry(payload: {
  text: string;
  scope_type: DiaryCaptureScopeType;
  scope_id?: string | null;
  linked_to?: string | null;
  links?: DiaryEntryLink[];
}): Promise<DiaryContextEntry> {
  const response = await api.post("/context/captures", payload);
  return response.data;
}

// Use correctCaptureCategory (PATCH /context/captures/{id}) for category changes.
// This function intentionally does not accept `type` to prevent bypassing the audit trail.
export async function updateDiaryContextEntry(
  id: number,
  payload: {
    text?: string;
    status?: DiaryStatus;
    scope_type?: DiaryCaptureScopeType;
    scope_id?: string | null;
    linked_to?: string | null;
    expires_at?: string | null;
  }
): Promise<DiaryContextEntry> {
  const response = await api.patch(`/context/captures/${id}`, payload);
  return response.data;
}

// Canonical category correction — sets user_corrected=true and preserves audit trail
export async function correctCaptureCategory(
  id: number,
  category: DiaryEntryType
): Promise<DiaryContextEntry> {
  const response = await api.patch(`/context/captures/${id}`, { type: category });
  return response.data;
}

export async function patchContextCapture(
  id: number,
  payload: {
    type?: DiaryEntryType;
    text?: string;
    scope_type?: DiaryCaptureScopeType;
    scope_id?: string | null;
    linked_to?: string | null;
    status?: DiaryStatus;
    expires_at?: string | null;
    links?: DiaryEntryLink[];
  }
): Promise<DiaryContextEntry> {
  const response = await api.patch(`/context/captures/${id}`, payload);
  return response.data;
}

export async function removeContextCaptureLink(
  id: number,
  params: {
    entity_type: string;
    entity_id: string;
  }
): Promise<DiaryContextEntry> {
  const response = await api.delete(`/context/captures/${id}/links`, { params });
  return response.data;
}

export async function fetchDiaryContacts(q?: string): Promise<DiaryContact[]> {
  const response = await api.get("/contacts", { params: { q: q || undefined } });
  return response.data;
}

export async function fetchContactByEmail(email: string): Promise<DiaryContact> {
  const response = await api.post("/contacts/lookup", { email });
  return response.data;
}

export async function createDiaryContact(payload: {
  name: string;
  email?: string | null;
  role?: string | null;
  organization?: string | null;
  notes?: string | null;
  category?: string | null;
}): Promise<DiaryContact> {
  const response = await api.post("/contacts", payload);
  return response.data;
}

export async function updateDiaryContact(
  id: number,
  payload: Partial<Pick<DiaryContact, "name" | "email" | "role" | "organization" | "notes" | "category">>
): Promise<DiaryContact> {
  const response = await api.put(`/contacts/${id}`, payload);
  return response.data;
}

export async function deleteDiaryContact(id: number): Promise<{ deleted: boolean; id: number }> {
  const response = await api.delete(`/contacts/${id}`);
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
