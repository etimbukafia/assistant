import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchVaultNotes,
  createVaultNote,
  updateVaultNote,
  fetchDiaryContextEntries,
  createDiaryContextEntry,
  deleteDiaryContextEntry,
  fetchDiaryContacts,
  createDiaryContact,
  deleteDiaryContact,
  VaultNoteType,
  DiaryEntryType,
  DiaryImportance,
  DiaryEntryLink,
} from "@/services/vault";

export const vaultKeys = {
  all: ["vault"] as const,
  notes: (params?: Record<string, unknown>) => [...vaultKeys.all, "notes", params] as const,
};

export const diaryKeys = {
  entries: (params?: Record<string, unknown>) => ["diary", "entries", params] as const,
  contacts: (q?: string) => ["diary", "contacts", q] as const,
};

export function useVaultNotes(params?: { note_type?: VaultNoteType; q?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: vaultKeys.notes(params),
    queryFn: () => fetchVaultNotes(params),
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
  };
}

// ── Diary hooks ─────────────────────────────────────────────────────────────

export function useDiaryEntries(params?: { type?: DiaryEntryType }) {
  return useQuery({
    queryKey: diaryKeys.entries(params),
    queryFn: () => fetchDiaryContextEntries(params),
  });
}

export function useDiaryContacts(q?: string) {
  return useQuery({
    queryKey: diaryKeys.contacts(q),
    queryFn: () => fetchDiaryContacts(q),
  });
}

export function useDiaryMutations() {
  const qc = useQueryClient();
  const invalidateEntries = () => qc.invalidateQueries({ queryKey: ["diary", "entries"] });
  const invalidateContacts = () => qc.invalidateQueries({ queryKey: ["diary", "contacts"] });

  const createEntry = useMutation({
    mutationFn: (payload: {
      type: DiaryEntryType;
      content: string;
      importance_level?: DiaryImportance;
      links?: DiaryEntryLink[];
    }) => createDiaryContextEntry(payload),
    onSuccess: invalidateEntries,
  });

  const deleteEntry = useMutation({
    mutationFn: (id: number) => deleteDiaryContextEntry(id),
    onSuccess: invalidateEntries,
  });

  const createContact = useMutation({
    mutationFn: (payload: { name: string; email?: string | null; role?: string | null; organization?: string | null; notes?: string | null }) =>
      createDiaryContact(payload),
    onSuccess: invalidateContacts,
  });

  const deleteContact = useMutation({
    mutationFn: (id: number) => deleteDiaryContact(id),
    onSuccess: invalidateContacts,
  });

  return { createEntry, deleteEntry, createContact, deleteContact };
}
