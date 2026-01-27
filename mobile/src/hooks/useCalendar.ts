/**
 * Calendar Hooks
 *
 * TanStack Query hooks for calendar operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import {
    fetchCalendarEvents,
    fetchCalendarEvent,
    fetchCalendarSettings,
    updateCalendarSettings,
    fetchUserCalendars,
    syncCalendar,
    generateFollowUps,
    createCalendarEvent,
    CalendarEventsResponse,
    CalendarEvent,
    CalendarSettings,
    CalendarSettingsUpdate,
    CalendarsResponse,
    SyncResponse,
    FollowUpsResponse,
    CreateEventRequest,
} from '@/src/services/calendar';
import { useAuth } from '@/src/context/AuthContext';

// Default calendar settings for sandbox mode
const SANDBOX_CALENDAR_SETTINGS: CalendarSettings = {
    working_hours_start: '09:00',
    working_hours_end: '17:00',
    default_meeting_duration: 30,
    buffer_minutes: 15,
    preferred_meeting_times: 'morning',
    default_timezone: 'America/New_York',
    calendar_ids: [],
};

export const calendarKeys = {
    all: ['calendar'] as const,
    events: () => [...calendarKeys.all, 'events'] as const,
    eventList: (status?: string) => [...calendarKeys.events(), status] as const,
    eventDetail: (id: number) => [...calendarKeys.events(), 'detail', id] as const,
    settings: () => [...calendarKeys.all, 'settings'] as const,
    calendars: () => [...calendarKeys.all, 'calendars'] as const,
};

// ================================
// Event Queries
// ================================

/**
 * Hook for fetching calendar events
 */
export function useCalendarEvents(status?: string, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: calendarKeys.eventList(status),
        queryFn: () => fetchCalendarEvents(status),
        enabled: options?.enabled ?? true,
    });
}

/**
 * Hook for fetching a single calendar event
 */
export function useCalendarEvent(eventId: number | null) {
    return useQuery({
        queryKey: calendarKeys.eventDetail(eventId!),
        queryFn: () => fetchCalendarEvent(eventId!),
        enabled: eventId !== null,
    });
}

// ================================
// Settings Queries & Mutations
// ================================

/**
 * Hook for fetching calendar settings
 */
export function useCalendarSettings(options?: { enabled?: boolean }) {
    const { isSandbox } = useAuth();

    const query = useQuery({
        queryKey: calendarKeys.settings(),
        queryFn: fetchCalendarSettings,
        enabled: (options?.enabled ?? true) && !isSandbox, // Disable API calls in sandbox mode
    });

    // Return sandbox data when in sandbox mode
    if (isSandbox) {
        return {
            ...query,
            data: SANDBOX_CALENDAR_SETTINGS,
            isLoading: false,
            error: null,
        };
    }

    return query;
}

/**
 * Hook for fetching user's Google calendars (for selection)
 */
export function useUserCalendars(options?: { enabled?: boolean }) {
    const { isSandbox } = useAuth();

    const query = useQuery({
        queryKey: calendarKeys.calendars(),
        queryFn: fetchUserCalendars,
        enabled: (options?.enabled ?? true) && !isSandbox, // Disable API calls in sandbox mode
        staleTime: 1000 * 60 * 30, // 30 minutes - calendar list rarely changes
    });

    // Return empty calendars when in sandbox mode
    if (isSandbox) {
        return {
            ...query,
            data: { calendars: [] },
            isLoading: false,
            error: null,
        };
    }

    return query;
}

/**
 * Hook for calendar mutations (sync, settings update, event creation, follow-ups)
 */
export function useCalendarMutations() {
    const queryClient = useQueryClient();

    const invalidateEvents = () => {
        queryClient.invalidateQueries({ queryKey: calendarKeys.events() });
    };

    const syncMutation = useMutation({
        mutationFn: (daysAhead?: number) => syncCalendar(daysAhead),
        onSuccess: invalidateEvents,
        onError: () => Alert.alert('Error', 'Failed to sync calendar'),
    });

    const updateSettingsMutation = useMutation({
        mutationFn: (settings: CalendarSettingsUpdate) => updateCalendarSettings(settings),
        onSuccess: (data) => {
            queryClient.setQueryData(calendarKeys.settings(), data);
        },
        onError: () => Alert.alert('Error', 'Failed to update calendar settings'),
    });

    const createEventMutation = useMutation({
        mutationFn: (request: CreateEventRequest) => createCalendarEvent(request),
        onSuccess: invalidateEvents,
        onError: () => Alert.alert('Error', 'Failed to create calendar event'),
    });

    const generateFollowUpsMutation = useMutation({
        mutationFn: (eventId: number) => generateFollowUps(eventId),
        onError: () => Alert.alert('Error', 'Failed to generate follow-ups'),
    });

    return {
        // Sync
        sync: syncMutation.mutate,
        syncAsync: syncMutation.mutateAsync,
        isSyncing: syncMutation.isPending,
        syncResult: syncMutation.data,

        // Settings
        updateSettings: updateSettingsMutation.mutate,
        updateSettingsAsync: updateSettingsMutation.mutateAsync,
        isUpdatingSettings: updateSettingsMutation.isPending,

        // Create Event
        createEvent: createEventMutation.mutate,
        createEventAsync: createEventMutation.mutateAsync,
        isCreatingEvent: createEventMutation.isPending,

        // Follow-ups
        generateFollowUps: generateFollowUpsMutation.mutate,
        generateFollowUpsAsync: generateFollowUpsMutation.mutateAsync,
        isGeneratingFollowUps: generateFollowUpsMutation.isPending,
        followUpsResult: generateFollowUpsMutation.data,
    };
}

/**
 * Combined hook for calendar settings screen
 */
export function useCalendarSettingsWithMutations(options?: { enabled?: boolean }) {
    const settingsQuery = useCalendarSettings(options);
    const calendarsQuery = useUserCalendars(options);
    const mutations = useCalendarMutations();

    return {
        // Settings data
        settings: settingsQuery.data,
        isLoadingSettings: settingsQuery.isLoading,
        settingsError: settingsQuery.error,

        // Calendars data
        calendars: calendarsQuery.data?.calendars || [],
        isLoadingCalendars: calendarsQuery.isLoading,

        // Mutations
        updateSettings: mutations.updateSettings,
        isUpdatingSettings: mutations.isUpdatingSettings,

        // Refetch
        refetch: () => {
            settingsQuery.refetch();
            calendarsQuery.refetch();
        },
    };
}
