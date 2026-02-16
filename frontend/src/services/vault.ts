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

export interface VaultProposal {
  id: number;
  user_id: string;
  target_note_id?: number | null;
  proposal_type: string;
  proposed_data: Record<string, unknown>;
  diff_summary?: string | null;
  source_type?: string | null;
  source_id?: string | null;
  confidence: number;
  priority: string;
  status: string;
  rejection_reason?: string | null;
  rejection_category?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  expires_at?: string | null;
}

export interface VaultStats {
  proposal_acceptance_rate: number;
  proposals_pending: number;
  proposals_stale_count: number;
  context_hit_rate: number;
  total_notes: number;
  notes_by_type: Record<string, number>;
  avg_proposals_per_day: number;
  top_rejection_categories: Array<{ category: string; count: number }>;
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

export async function fetchVaultProposals(status = "pending"): Promise<{ proposals: VaultProposal[]; total: number }> {
  const response = await api.get("/vault/proposals", { params: { status } });
  return response.data;
}

export async function bulkApproveVaultProposals(proposal_ids: number[]): Promise<{ approved: number; requested: number }> {
  const response = await api.post("/vault/proposals/bulk-approve", { proposal_ids });
  return response.data;
}

export async function approveVaultProposal(id: number): Promise<VaultProposal> {
  const response = await api.post(`/vault/proposals/${id}/approve`);
  return response.data;
}

export async function rejectVaultProposal(id: number, payload: { category: string; reason?: string }): Promise<VaultProposal> {
  const response = await api.post(`/vault/proposals/${id}/reject`, payload);
  return response.data;
}

export async function fetchVaultContactCandidates(): Promise<{ contacts: Array<{ email: string; name?: string; message_count: number }> }> {
  const response = await api.get("/vault/contacts/candidates");
  return response.data;
}

export async function promoteVaultContact(email: string, display_name?: string): Promise<VaultNote> {
  const response = await api.post(`/vault/contacts/${encodeURIComponent(email)}/promote`, { display_name });
  return response.data;
}

export async function fetchVaultStats(): Promise<VaultStats> {
  const response = await api.get("/vault/stats");
  return response.data;
}
