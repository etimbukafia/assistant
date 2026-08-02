import { useQuery } from "@tanstack/react-query";
import { fetchContactBrief, fetchContactTimeline } from "@/services/contacts";

export const contactKeys = {
  brief: (id: number) => ["contact", "brief", id] as const,
  timeline: (id: number) => ["contact", "timeline", id] as const,
};

export function useContactBrief(contactId: number | null) {
  return useQuery({
    queryKey: contactKeys.brief(contactId!),
    queryFn: () => fetchContactBrief(contactId!),
    enabled: !!contactId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useContactTimeline(contactId: number | null) {
  return useQuery({
    queryKey: contactKeys.timeline(contactId!),
    queryFn: () => fetchContactTimeline(contactId!),
    enabled: !!contactId,
    staleTime: 5 * 60 * 1000,
  });
}
