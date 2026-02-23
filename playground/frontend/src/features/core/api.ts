import type {
  CalendarEvent,
  Contact,
  ContextEntry,
  ContextEntryType,
  ContextEntityType,
  EmailDraftResult,
  EntityReference,
  EntityReferenceType,
  InboxMessage,
  InboxThread,
  MeetingBriefResult,
  ThreadIntelligenceResult,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_PLAYGROUND_API_BASE || "http://localhost:8010/api";
export const API_V1_BASE = process.env.NEXT_PUBLIC_PLAYGROUND_API_V1_BASE || "http://localhost:8010/v1";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = (data as { detail?: string })?.detail;
    throw new Error(detail || "Request failed");
  }

  return response.json() as Promise<T>;
}

async function apiFetchV1<T>(path: string, userId: string, options?: RequestInit): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    "X-User-Id": userId,
    ...(options?.headers || {}),
  };

  const response = await fetch(`${API_V1_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = (data as { detail?: string })?.detail;
    throw new Error(detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function fetchDiaryData(userId: string) {
  const params = `user_id=${encodeURIComponent(userId)}`;
  const [entries, contacts, entities, threads, events] = await Promise.all([
    apiFetch<ContextEntry[]>(`/context-entries?${params}`),
    apiFetch<Contact[]>(`/contacts?${params}`),
    apiFetch<EntityReference[]>(`/entity-references?${params}`),
    apiFetch<InboxThread[]>(`/inbox/threads?${params}`),
    apiFetch<CalendarEvent[]>(`/calendar/events?${params}`),
  ]);
  return { entries, contacts, entities, threads, events };
}

export async function createContact(userId: string, payload: Partial<Contact>) {
  return apiFetch<Contact>("/contacts", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      name: payload.name?.trim(),
      email: payload.email?.trim() || null,
      role: payload.role?.trim() || null,
      organization: payload.organization?.trim() || null,
      notes: payload.notes?.trim() || null,
    }),
  });
}

export async function deleteContact(contactId: number) {
  return apiFetch<{ deleted: boolean; id: number }>(`/contacts/${contactId}`, { method: "DELETE" });
}

export async function createEntityReference(userId: string, payload: Partial<EntityReference>) {
  return apiFetch<EntityReference>("/entity-references", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      entity_type: payload.entity_type,
      display_name: payload.display_name?.trim(),
      ref: payload.ref?.trim(),
      notes: payload.notes?.trim() || null,
    }),
  });
}

export async function deleteEntityReference(entityId: number) {
  return apiFetch<{ deleted: boolean; id: number }>(`/entity-references/${entityId}`, { method: "DELETE" });
}

export async function createContextEntry(userId: string, payload: {
  type: ContextEntryType;
  content: string;
  entity_type: ContextEntityType;
  entity_id?: string | null;
  importance_level: "low" | "normal" | "high";
  status?: "active" | "resolved" | "stale" | "archived";
  expires_at?: string | null;
}) {
  return apiFetch<ContextEntry>("/context-entries", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      type: payload.type,
      content: payload.content,
      entity_type: payload.entity_type,
      entity_id: payload.entity_type === "executive" || payload.entity_type === "assistant" ? null : payload.entity_id,
      created_by: "You",
      importance_level: payload.importance_level,
      status: payload.status || "active",
      expires_at: payload.expires_at || null,
    }),
  });
}

export async function updateContextEntry(entryId: number, payload: {
  content: string;
  importance_level: "low" | "normal" | "high";
  status?: "active" | "resolved" | "stale" | "archived";
  expires_at?: string | null;
}) {
  return apiFetch<ContextEntry>(`/context-entries/${entryId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteContextEntry(entryId: number) {
  return apiFetch<{ deleted: boolean; id: number }>(`/context-entries/${entryId}`, { method: "DELETE" });
}

export async function updateThreadStatus(userId: string, threadId: string, status: "open" | "waiting" | "closed") {
  return apiFetch<InboxThread>(`/inbox/threads/${encodeURIComponent(threadId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ user_id: userId, status }),
  });
}

export async function fetchThreadMessages(userId: string, threadId: string) {
  return apiFetch<InboxMessage[]>(`/inbox/threads/${encodeURIComponent(threadId)}/messages?user_id=${encodeURIComponent(userId)}`);
}

export async function fetchThreadIntelligence(userId: string, threadId: string) {
  return apiFetch<ThreadIntelligenceResult>(`/inbox/threads/${encodeURIComponent(threadId)}/intelligence?user_id=${encodeURIComponent(userId)}`);
}

export async function draftEmail(userId: string, payload: {
  subject: string;
  intent: string;
  recipient?: string | null;
  thread_id?: string | null;
  message_id?: string | null;
  thread?: string | null;
  message?: string | null;
}) {
  return apiFetch<EmailDraftResult>("/action-tools/email-draft", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, ...payload }),
  });
}

export async function generateMeetingBrief(userId: string, payload: {
  event_id?: string | null;
  meeting_subject?: string | null;
  include_recent_context?: boolean;
}) {
  return apiFetch<MeetingBriefResult>("/action-tools/meeting-brief", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, ...payload }),
  });
}

export async function fetchMentionSuggestions(userId: string, query = "", limit = 8) {
  const params = new URLSearchParams({
    q: query.trim(),
    limit: String(limit),
    session_id: "default",
    user_id: userId,
  });
  const response = await fetch(`${API_V1_BASE}/chat/mentions?${params.toString()}`, {
    method: "GET",
    headers: { "X-User-Id": userId },
  });
  if (!response.ok) {
    throw new Error("Failed to load mentions");
  }
  return response.json() as Promise<{
    kind: string;
    ref: string;
    label: string;
    display_label?: string;
    subtitle?: string;
  }[]>;
}

export async function createChatSession(userId: string, sessionType: "command" | "reflection" = "command") {
  return apiFetchV1<{ id: string }>("/chat/sessions", userId, {
    method: "POST",
    body: JSON.stringify({ session_type: sessionType }),
  });
}

export async function sendChatMessageV1(payload: {
  user_id: string;
  session_id: string;
  content: string;
  mentions?: Array<{ kind: string; ref: string; label?: string }>;
}) {
  return apiFetchV1<{ status: string; response?: string }>(
    `/chat/sessions/${encodeURIComponent(payload.session_id)}/messages`,
    payload.user_id,
    {
      method: "POST",
      body: JSON.stringify({
        content: payload.content,
        mentions: payload.mentions || [],
      }),
    },
  );
}

export async function streamChatMessage(payload: {
  user_id: string;
  session_id: string;
  content: string;
  mentions?: Array<{ kind: string; ref: string; label?: string }>;
  onEvent: (event: {
    event_id: string;
    session_id: string;
    message_id?: number | null;
    type: string;
    payload: Record<string, unknown>;
    ts: string;
  }) => void;
}) {
  const response = await fetch(
    `${API_V1_BASE}/chat/sessions/${encodeURIComponent(payload.session_id)}/messages/stream`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": payload.user_id,
      },
      body: JSON.stringify({
        content: payload.content,
        mentions: payload.mentions || [],
      }),
    },
  );

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = (data as { detail?: string })?.detail;
    throw new Error(detail || "Failed to send message");
  }

  if (!response.body) {
    throw new Error("Streaming not supported in this browser");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "message";
  let dataBuffer = "";
  const seen = new Set<string>();

  const flushEvent = () => {
    if (!dataBuffer.trim()) {
      dataBuffer = "";
      eventType = "message";
      return;
    }
    try {
      const parsed = JSON.parse(dataBuffer);
      const key = String(parsed.event_id || "");
      if (!key || seen.has(key)) {
        dataBuffer = "";
        eventType = "message";
        return;
      }
      seen.add(key);
      payload.onEvent({
        ...parsed,
        type: parsed.type || eventType,
      });
    } catch {
      // ignore malformed chunk
    } finally {
      dataBuffer = "";
      eventType = "message";
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      flushEvent();
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) {
        flushEvent();
        continue;
      }
      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim() || "message";
        continue;
      }
      if (line.startsWith("data:")) {
        const chunk = line.slice(5).trim();
        dataBuffer = dataBuffer ? `${dataBuffer}\n${chunk}` : chunk;
      }
    }
  }
}

export async function sendChatMessage(payload: {
  message: string;
  user_id: string;
  session_id: string;
  current_state?: Record<string, unknown>;
  mentions?: Array<{ kind: string; ref: string; label?: string }>;
}) {
  return apiFetch<{ reply: string; gate?: unknown }>("/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
