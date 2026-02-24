import { useMutation, useQuery, useQueryClient, QueryKey } from "@tanstack/react-query";
import {
  fetchVaultNotes,
  createVaultNote,
  updateVaultNote,
  fetchDiaryContextEntries,
  createDiaryContextEntry,
  updateDiaryContextEntry,
  deleteDiaryContextEntry,
  fetchDiaryContacts,
  fetchContactByEmail,
  createDiaryContact,
  updateDiaryContact,
  deleteDiaryContact,
  VaultNoteType,
  DiaryEntryType,
  DiaryImportance,
  DiaryEntryLink,
  DiaryContextEntry,
  DiaryContact,
} from "@/services/vault";

export const vaultKeys = {
  all: ["vault"] as const,
  notes: (params?: Record<string, unknown>) => [...vaultKeys.all, "notes", params] as const,
};

export const diaryKeys = {
  entries: (params?: Record<string, unknown>) => ["diary", "entries", params] as const,
  contacts: (q?: string) => ["diary", "contacts", q] as const,
  contactByEmail: (email: string) => ["diary", "contact-by-email", email] as const,
};

const ENTRIES_KEY = ["diary", "entries"] as const;
const CONTACTS_KEY = ["diary", "contacts"] as const;

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

export function useContactByEmail(email: string | null) {
  return useQuery({
    queryKey: diaryKeys.contactByEmail(email || ""),
    queryFn: () => fetchContactByEmail(email!),
    enabled: !!email,
    retry: false,
  });
}

export function useDiaryMutations() {
  const qc = useQueryClient();

  type EntriesSnapshot = [QueryKey, DiaryContextEntry[] | undefined][];
  type ContactsSnapshot = [QueryKey, DiaryContact[] | undefined][];

  function rollbackEntries(snapshot: EntriesSnapshot) {
    for (const [key, data] of snapshot) qc.setQueryData(key, data);
  }
  function rollbackContacts(snapshot: ContactsSnapshot) {
    for (const [key, data] of snapshot) qc.setQueryData(key, data);
  }

  const createEntry = useMutation({
    mutationFn: (payload: {
      type: DiaryEntryType;
      content: string;
      importance_level?: DiaryImportance;
      expires_at?: string | null;
      links?: DiaryEntryLink[];
    }) => createDiaryContextEntry(payload),
    onMutate: async (payload) => {
      await qc.cancelQueries({ queryKey: ENTRIES_KEY });
      const snapshot = qc.getQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }) as EntriesSnapshot;
      const optimistic: DiaryContextEntry = {
        id: -Date.now(),
        user_id: "",
        type: payload.type,
        content: payload.content,
        entity_type: "global",
        entity_id: null,
        linked_to: null,
        created_by: "You",
        importance_level: payload.importance_level ?? "normal",
        status: "active",
        expires_at: payload.expires_at ?? null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        links: payload.links ?? [],
      };
      qc.setQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }, (old) =>
        old ? [optimistic, ...old] : [optimistic]
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackEntries(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: ENTRIES_KEY }),
  });

  const deleteEntry = useMutation({
    mutationFn: (id: number) => deleteDiaryContextEntry(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ENTRIES_KEY });
      const snapshot = qc.getQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }) as EntriesSnapshot;
      qc.setQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }, (old) =>
        old ? old.filter((e) => e.id !== id) : old
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackEntries(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: ENTRIES_KEY }),
  });

  const updateEntry = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof updateDiaryContextEntry>[1] }) =>
      updateDiaryContextEntry(id, payload),
    onMutate: async ({ id, payload }) => {
      await qc.cancelQueries({ queryKey: ENTRIES_KEY });
      const snapshot = qc.getQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }) as EntriesSnapshot;
      qc.setQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }, (old) =>
        old
          ? old.map((e) => e.id === id ? { ...e, ...payload, updated_at: new Date().toISOString() } : e)
          : old
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackEntries(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: ENTRIES_KEY }),
  });

  const createContact = useMutation({
    mutationFn: (payload: { name: string; email?: string | null; role?: string | null; organization?: string | null; notes?: string | null; category?: string | null }) =>
      createDiaryContact(payload),
    onMutate: async (payload) => {
      await qc.cancelQueries({ queryKey: CONTACTS_KEY });
      const snapshot = qc.getQueriesData<DiaryContact[]>({ queryKey: CONTACTS_KEY }) as ContactsSnapshot;
      const optimistic = {
        id: -Date.now(),
        user_id: "",
        name: payload.name,
        email: payload.email ?? null,
        role: payload.role ?? null,
        organization: payload.organization ?? null,
        notes: payload.notes ?? null,
        category: (payload.category as DiaryContact["category"]) ?? null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      } as DiaryContact;
      qc.setQueriesData<DiaryContact[]>({ queryKey: CONTACTS_KEY }, (old) =>
        old ? [optimistic, ...old] : [optimistic]
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackContacts(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: CONTACTS_KEY }),
  });

  const deleteContact = useMutation({
    mutationFn: (id: number) => deleteDiaryContact(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: CONTACTS_KEY });
      const snapshot = qc.getQueriesData<DiaryContact[]>({ queryKey: CONTACTS_KEY }) as ContactsSnapshot;
      qc.setQueriesData<DiaryContact[]>({ queryKey: CONTACTS_KEY }, (old) =>
        old ? old.filter((c) => c.id !== id) : old
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackContacts(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: CONTACTS_KEY }),
  });

  const updateContact = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof updateDiaryContact>[1] }) =>
      updateDiaryContact(id, payload),
    onMutate: async ({ id, payload }) => {
      await qc.cancelQueries({ queryKey: CONTACTS_KEY });
      const snapshot = qc.getQueriesData<DiaryContact[]>({ queryKey: CONTACTS_KEY }) as ContactsSnapshot;
      qc.setQueriesData<DiaryContact[]>({ queryKey: CONTACTS_KEY }, (old) =>
        old
          ? old.map((c) => c.id === id ? { ...c, ...payload, updated_at: new Date().toISOString() } : c)
          : old
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackContacts(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: CONTACTS_KEY }),
  });

  return { createEntry, updateEntry, deleteEntry, createContact, updateContact, deleteContact };
}
