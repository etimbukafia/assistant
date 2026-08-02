import { api } from "./api";

export interface ContactResponse {
  id: number;
  user_id: string;
  name: string;
  email?: string | null;
  role?: string | null;
  organization?: string | null;
  notes?: string | null;
  category?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContactBriefSignal {
  key: string;
  label: string;
  severity: "info" | "warning" | "urgent";
  detail?: string | null;
}

export interface ContactBriefMemoryItem {
  id: string;
  content: string;
  source_type: string;
  source_ref?: string | null;
  created_at?: string | null;
}

export interface ContactBriefCommitment {
  id: string;
  title: string;
  detail?: string | null;
  status: string;
  source_type: string;
  source_ref?: string | null;
  due_at?: string | null;
  created_at?: string | null;
}

export interface ContactBriefDecision {
  id: string;
  decision: string;
  source_type: string;
  source_ref?: string | null;
  created_at?: string | null;
}

export interface ContactBriefInteraction {
  id: string;
  interaction_type: string;
  subject?: string | null;
  summary?: string | null;
  thread_id?: string | null;
  thread_resolved?: boolean | null;
  occurred_at: string;
  needs_reply: boolean;
}

export interface ContactBriefEvent {
  id: number;
  title: string;
  start_time: string;
  end_time: string;
  location?: string | null;
  organizer?: string | null;
  participant_count: number;
}

export interface ContactBriefSummary {
  headline: string;
  category?: string | null;
  role?: string | null;
  organization?: string | null;
  manual_notes?: string | null;
  relationship_notes: string[];
  preferred_tone?: string | null;
}

export interface ContactBriefStats {
  total_messages: number;
  total_threads: number;
  open_tasks: number;
  avg_response_latency_hours?: number | null;
}

export interface ContactBrief {
  contact: ContactResponse;
  summary: ContactBriefSummary;
  stats: ContactBriefStats;
  preferences: ContactBriefMemoryItem[];
  commitments: ContactBriefCommitment[];
  decisions: ContactBriefDecision[];
  recent_interactions: ContactBriefInteraction[];
  upcoming_events: ContactBriefEvent[];
  signals: ContactBriefSignal[];
}

export interface ContactTimelineItem {
  id: string;
  kind: string;
  title: string;
  detail?: string | null;
  occurred_at: string;
  source_type: string;
  source_ref?: string | null;
  source_resolved?: boolean | null;
  status?: string | null;
}

export interface ContactTimeline {
  contact: ContactResponse;
  timeline: ContactTimelineItem[];
}

export async function fetchContactBrief(contactId: number): Promise<ContactBrief> {
  const response = await api.get(`/contacts/${contactId}/brief`);
  return response.data;
}

export async function fetchContactTimeline(contactId: number): Promise<ContactTimeline> {
  const response = await api.get(`/contacts/${contactId}/timeline`);
  return response.data;
}
