export type ContextEntryType = "decision" | "commitment" | "preferences" | "insight" | "relationships";
export type ContextEntityType = "assistant" | "contact" | "thread" | "message" | "event" | "executive";
export type ContextEntryStatus = "active" | "resolved" | "stale" | "archived";

export type ContextEntry = {
  id: number;
  user_id: string;
  type: ContextEntryType;
  content: string;
  entity_type: ContextEntityType;
  entity_id?: string | null;
  created_by: "Teeks" | "You";
  created_at: string;
  importance_level: "low" | "normal" | "high";
  status: ContextEntryStatus;
  expires_at?: string | null;
};

export type Contact = {
  id: number;
  user_id: string;
  name: string;
  email?: string | null;
  role?: string | null;
  organization?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type EntityReferenceType = "thread" | "message" | "event";

export type EntityReference = {
  id: number;
  user_id: string;
  entity_type: EntityReferenceType;
  display_name: string;
  ref: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type InboxThread = {
  id: number;
  user_id: string;
  thread_id: string;
  subject: string;
  snippet?: string | null;
  last_sender?: string | null;
  last_received_at: string;
  unread_count: number;
  status: "open" | "waiting" | "closed";
};

export type InboxMessage = {
  id: number;
  user_id: string;
  message_id: string;
  thread_id: string;
  subject: string;
  sender: string;
  recipients?: string | null;
  body_preview?: string | null;
  sent_at: string;
  direction: "inbound" | "outbound" | "draft";
  needs_reply: number;
};

export type CalendarEvent = {
  id: number;
  user_id: string;
  event_id: string;
  subject: string;
  description?: string | null;
  location?: string | null;
  attendees?: string | null;
  start_at: string;
  end_at: string;
  status: "confirmed" | "tentative" | "cancelled";
};

export type EmailDraftResult = {
  subject: string;
  intent: string;
  recipient?: string | null;
  thread_id?: string | null;
  message_id?: string | null;
  body: string;
  context_entries?: Array<Record<string, unknown>>;
};

export type MeetingBriefResult = {
  event_id?: string | null;
  meeting_subject?: string | null;
  summary: string;
  participants: string[];
  agenda: string[];
  decisions: string[];
  commitments: string[];
  risks: string[];
  open_items: string[];
};

export type ThreadIntelligenceResult = {
  thread_id: string;
  subject?: string;
  summary: string;
  needs_reply: boolean;
  action_points: string[];
  decisions: string[];
  commitments: string[];
  risks: string[];
  relationships?: string[];
  participants: string[];
  message_count: number;
  latest_message_id?: string | null;
  context_entries?: Array<Record<string, unknown>>;
};

export type GateDecision = {
  use_context: boolean;
  context_level: "none" | "light" | "full";
  context_types: string[];
  reason: string;
};

export type MentionKind = "contact" | "event" | "thread" | "message";

export type MentionChip = {
  kind: MentionKind;
  ref: string;
  label: string;
};

export type MentionSuggestion = MentionChip & {
  display_label?: string;
  subtitle?: string;
};

export type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  timestamp: string;
  gate?: GateDecision | null;
};

export type DiaryPage = "home" | "remember" | "contacts" | "inbox" | "calendar" | "chat";
