import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchVaultNotes,
  createVaultNote,
  updateVaultNote,
  fetchVaultProposals,
  bulkApproveVaultProposals,
  approveVaultProposal,
  rejectVaultProposal,
  fetchVaultContactCandidates,
  promoteVaultContact,
  fetchVaultStats,
  VaultNoteType,
} from "@/services/vault";

export const vaultKeys = {
  all: ["vault"] as const,
  notes: (params?: Record<string, unknown>) => [...vaultKeys.all, "notes", params] as const,
  proposals: (status = "pending") => [...vaultKeys.all, "proposals", status] as const,
  contacts: () => [...vaultKeys.all, "contacts"] as const,
  stats: () => [...vaultKeys.all, "stats"] as const,
};

export function useVaultNotes(params?: { note_type?: VaultNoteType; q?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: vaultKeys.notes(params),
    queryFn: () => fetchVaultNotes(params),
  });
}

export function useVaultProposals(status = "pending") {
  return useQuery({
    queryKey: vaultKeys.proposals(status),
    queryFn: () => fetchVaultProposals(status),
  });
}

export function useVaultContacts() {
  return useQuery({
    queryKey: vaultKeys.contacts(),
    queryFn: fetchVaultContactCandidates,
  });
}

export function useVaultStats() {
  return useQuery({
    queryKey: vaultKeys.stats(),
    queryFn: fetchVaultStats,
  });
}

export function useVaultMutations() {
  const qc = useQueryClient();
  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: vaultKeys.all });
  };

  return {
    createNote: useMutation({
      mutationFn: createVaultNote,
      onSuccess: invalidateAll,
    }),
    updateNote: useMutation({
      mutationFn: ({ noteId, payload }: { noteId: number; payload: Parameters<typeof updateVaultNote>[1] }) =>
        updateVaultNote(noteId, payload),
      onSuccess: invalidateAll,
    }),
    approveProposal: useMutation({
      mutationFn: approveVaultProposal,
      onSuccess: invalidateAll,
    }),
    bulkApprove: useMutation({
      mutationFn: bulkApproveVaultProposals,
      onSuccess: invalidateAll,
    }),
    rejectProposal: useMutation({
      mutationFn: ({ id, payload }: { id: number; payload: { category: string; reason?: string } }) =>
        rejectVaultProposal(id, payload),
      onSuccess: invalidateAll,
    }),
    promoteContact: useMutation({
      mutationFn: ({ email, display_name }: { email: string; display_name?: string }) =>
        promoteVaultContact(email, display_name),
      onSuccess: invalidateAll,
    }),
  };
}
