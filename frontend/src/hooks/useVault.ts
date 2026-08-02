import { useMutation, useQuery, useQueryClient, QueryKey } from "@tanstack/react-query";
import {
  fetchVaultNotes,
  createVaultNote,
  updateVaultNote,
  fetchDiaryContextEntries,
  createDiaryContextEntry,
  updateDiaryContextEntry,
  correctCaptureCategory,
  patchContextCapture,
  removeContextCaptureLink,
  fetchDiaryContacts,
  fetchContactByEmail,
  createDiaryContact,
  updateDiaryContact,
  deleteDiaryContact,
  VaultNoteType,
  DiaryEntryType,
  DiaryCaptureScopeType,
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
  contactLookup: (email?: string | null) => ["diary", "contact-lookup", hashDiaryContactLookup(email)] as const,
};

const ENTRIES_KEY = ["diary", "entries"] as const;
const CONTACTS_KEY = ["diary", "contacts"] as const;
const VISIBLE_ENTRY_STATUSES = new Set<DiaryContextEntry["status"]>(["active", "stale"]);

function hashDiaryContactLookup(email?: string | null): string {
  const normalized = (email || "").trim().toLowerCase();
  if (!normalized) return "none";

  let hash = 2166136261;
  for (let i = 0; i < normalized.length; i += 1) {
    hash ^= normalized.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16);
}

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

export function useDiaryEntries(
  params?: { type?: DiaryEntryType; entity_type?: DiaryContextEntry["entity_type"]; entity_id?: string },
  options?: { refetchInterval?: number | false }
) {
  return useQuery({
    queryKey: diaryKeys.entries(params),
    queryFn: () => fetchDiaryContextEntries(params),
    refetchOnWindowFocus: true,
    refetchInterval: options?.refetchInterval,
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
    queryKey: diaryKeys.contactLookup(email),
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
      text: string;
      scope_type: DiaryCaptureScopeType;
      scope_id?: string | null;
      linked_to?: string | null;
      links?: DiaryEntryLink[];
    }) => createDiaryContextEntry(payload),
    onMutate: async (payload) => {
      await qc.cancelQueries({ queryKey: ENTRIES_KEY });
      const snapshot = qc.getQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }) as EntriesSnapshot;
      const optimistic: DiaryContextEntry = {
        id: -Date.now(),
        user_id: "",
        type: "insight",
        content: payload.text,
        raw_text: payload.text,
        entity_type: payload.scope_type,
        entity_id: payload.scope_id ?? null,
        linked_to: payload.linked_to ?? null,
        created_by: "You",
        status: "active",
        classification_status: "pending",
        classification_confidence: null,
        user_corrected: false,
        expires_at: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        links: (payload.links ?? []).map((link) => ({
          ...link,
          source: link.source ?? "user",
        })),
      };
      qc.setQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }, (old) =>
        old ? [optimistic, ...old] : [optimistic]
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
      const nextStatus = payload.status;
      qc.setQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }, (old) =>
        old
          ? old
              .map((e) => e.id === id ? {
                ...e,
                content: payload.text ?? e.content,
                raw_text: payload.text ?? e.raw_text,
                status: nextStatus ?? e.status,
                entity_type: payload.scope_type ?? e.entity_type,
                entity_id: payload.scope_id ?? e.entity_id,
                linked_to: payload.linked_to ?? e.linked_to,
                expires_at: payload.expires_at ?? e.expires_at,
                updated_at: new Date().toISOString(),
              } : e)
              .filter((entry) => !nextStatus || VISIBLE_ENTRY_STATUSES.has(entry.status))
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

  const correctCategory = useMutation({
    mutationFn: ({ id, category }: { id: number; category: DiaryEntryType }) =>
      correctCaptureCategory(id, category),
    onMutate: async ({ id, category }) => {
      await qc.cancelQueries({ queryKey: ENTRIES_KEY });
      const snapshot = qc.getQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }) as EntriesSnapshot;
      qc.setQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }, (old) =>
        old
          ? old.map((e) =>
              e.id === id
                ? { ...e, type: category, classification_status: "user_corrected" as const, user_corrected: true, updated_at: new Date().toISOString() }
                : e
            )
          : old
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackEntries(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: ENTRIES_KEY }),
  });

  const updateCapture = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof patchContextCapture>[1] }) =>
      patchContextCapture(id, payload),
    onMutate: async ({ id, payload }) => {
      await qc.cancelQueries({ queryKey: ENTRIES_KEY });
      const snapshot = qc.getQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }) as EntriesSnapshot;
      const nextStatus = payload.status;
      qc.setQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }, (old) =>
        old
          ? old
              .map((entry) =>
                entry.id === id
                  ? {
                      ...entry,
                      ...(payload.type ? { type: payload.type } : null),
                      ...(payload.text ? { content: payload.text, raw_text: payload.text } : null),
                      ...(payload.scope_type ? { entity_type: payload.scope_type } : null),
                      ...(payload.scope_id !== undefined ? { entity_id: payload.scope_id } : null),
                      ...(payload.linked_to !== undefined ? { linked_to: payload.linked_to } : null),
                      ...(payload.status ? { status: payload.status } : null),
                      ...(payload.expires_at !== undefined ? { expires_at: payload.expires_at } : null),
                      ...(payload.links ? { links: payload.links } : null),
                      updated_at: new Date().toISOString(),
                    }
                  : entry
              )
              .filter((entry) => !nextStatus || VISIBLE_ENTRY_STATUSES.has(entry.status))
          : old
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackEntries(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: ENTRIES_KEY }),
  });

  const removeCaptureLink = useMutation({
    mutationFn: ({ id, entityType, entityId }: { id: number; entityType: string; entityId: string }) =>
      removeContextCaptureLink(id, { entity_type: entityType, entity_id: entityId }),
    onMutate: async ({ id, entityType, entityId }) => {
      await qc.cancelQueries({ queryKey: ENTRIES_KEY });
      const snapshot = qc.getQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }) as EntriesSnapshot;
      qc.setQueriesData<DiaryContextEntry[]>({ queryKey: ENTRIES_KEY }, (old) =>
        old
          ? old.map((entry) =>
              entry.id === id
                ? {
                    ...entry,
                    links: (entry.links ?? []).filter(
                      (link) => !(link.entity_type === entityType && link.entity_id === entityId)
                    ),
                    updated_at: new Date().toISOString(),
                  }
                : entry
            )
          : old
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => { if (ctx) rollbackEntries(ctx.snapshot); },
    onSettled: () => qc.invalidateQueries({ queryKey: ENTRIES_KEY }),
  });

  return {
    createEntry,
    updateEntry,
    updateCapture,
    removeCaptureLink,
    correctCategory,
    createContact,
    updateContact,
    deleteContact,
  };
}
