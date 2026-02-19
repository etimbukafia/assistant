"use client";

import { useEffect, useMemo, useState } from "react";
import { usePlayground } from "../core/PlaygroundProvider";
import { generateMeetingBrief } from "../core/api";
import type { CalendarEvent, MeetingBriefResult } from "../core/types";
import { endOfDay, endOfMonth, endOfWeek, startOfDay, startOfMonth, startOfWeek } from "../core/utils";

type CalendarView = "month" | "week" | "day" | "list";

export default function CalendarPage() {
  const { userId, events } = usePlayground();
  const [calendarView, setCalendarView] = useState<CalendarView>("month");
  const [calendarAnchorDate, setCalendarAnchorDate] = useState<Date>(new Date());
  const [selectedEventId, setSelectedEventId] = useState<string>("");
  const [meetingBrief, setMeetingBrief] = useState<MeetingBriefResult | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const calendarWindow = useMemo(() => {
    if (calendarView === "month") {
      return { start: startOfMonth(calendarAnchorDate), end: endOfMonth(calendarAnchorDate) };
    }
    if (calendarView === "week") {
      return { start: startOfWeek(calendarAnchorDate), end: endOfWeek(calendarAnchorDate) };
    }
    if (calendarView === "day") {
      return { start: startOfDay(calendarAnchorDate), end: endOfDay(calendarAnchorDate) };
    }
    const start = startOfDay(calendarAnchorDate);
    const end = new Date(start);
    end.setDate(start.getDate() + 29);
    return { start, end: endOfDay(end) };
  }, [calendarAnchorDate, calendarView]);

  const calendarVisibleEvents = useMemo(
    () => events
      .filter((event) => {
        const start = new Date(event.start_at).getTime();
        return start >= calendarWindow.start.getTime() && start <= calendarWindow.end.getTime();
      })
      .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
    [events, calendarWindow],
  );

  const selectedEvent = useMemo(
    () => events.find((event) => event.event_id === selectedEventId) || null,
    [events, selectedEventId],
  );

  const calendarRangeLabel = useMemo(() => {
    const monthLabel = calendarAnchorDate.toLocaleDateString(undefined, { month: "long", year: "numeric" });
    if (calendarView === "month") {
      return monthLabel;
    }
    if (calendarView === "day") {
      return calendarAnchorDate.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
    }
    const startLabel = calendarWindow.start.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    const endLabel = calendarWindow.end.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    return `${startLabel} - ${endLabel}`;
  }, [calendarAnchorDate, calendarView, calendarWindow.end, calendarWindow.start]);

  useEffect(() => {
    if (!calendarVisibleEvents.length) {
      setSelectedEventId("");
      return;
    }
    if (!calendarVisibleEvents.some((event) => event.event_id === selectedEventId)) {
      setSelectedEventId(calendarVisibleEvents[0].event_id);
    }
  }, [calendarVisibleEvents, selectedEventId]);

  async function handleBrief(eventItem: CalendarEvent) {
    const scopedUserId = userId.trim();
    if (!scopedUserId) {
      return;
    }
    setSelectedEventId(eventItem.event_id);
    setActionLoading(true);
    try {
      const data = await generateMeetingBrief(scopedUserId, {
        event_id: eventItem.event_id,
        meeting_subject: eventItem.subject,
        include_recent_context: true,
      });
      setMeetingBrief(data);
    } finally {
      setActionLoading(false);
    }
  }

  function shiftCalendarWindow(direction: -1 | 1) {
    setCalendarAnchorDate((prev) => {
      const next = new Date(prev);
      if (calendarView === "month") {
        next.setMonth(prev.getMonth() + direction);
      } else if (calendarView === "week") {
        next.setDate(prev.getDate() + direction * 7);
      } else if (calendarView === "day") {
        next.setDate(prev.getDate() + direction);
      } else {
        next.setDate(prev.getDate() + direction * 30);
      }
      return next;
    });
  }

  return (
    <div className="page-panel">
      <section className="memory-block">
        <div className="section-toolbar">
          <h2 className="section-title">Calendar</h2>
          <div className="segmented-control">
            {(["month", "week", "day", "list"] as CalendarView[]).map((view) => (
              <button
                key={view}
                className={`segmented-button ${calendarView === view ? "active" : ""}`}
                onClick={() => setCalendarView(view)}
              >
                {view}
              </button>
            ))}
          </div>
        </div>

        <div className="calendar-nav">
          <button className="button secondary" onClick={() => shiftCalendarWindow(-1)}>Prev</button>
          <div className="calendar-label">{calendarRangeLabel}</div>
          <button className="button secondary" onClick={() => setCalendarAnchorDate(new Date())}>Today</button>
          <button className="button secondary" onClick={() => shiftCalendarWindow(1)}>Next</button>
        </div>

        <div className="calendar-layout">
          <div className="calendar-list">
            {calendarVisibleEvents.length === 0 ? (
              <div className="entry">
                <div className="entry-meta">No events in this range.</div>
              </div>
            ) : (
              calendarVisibleEvents.map((eventItem) => (
                <button
                  key={eventItem.event_id}
                  type="button"
                  className={`entry calendar-row ${selectedEventId === eventItem.event_id ? "is-selected" : ""}`}
                  onClick={() => {
                    setSelectedEventId(eventItem.event_id);
                    setMeetingBrief(null);
                  }}
                >
                  <div className="entry-meta">{new Date(eventItem.start_at).toLocaleString()} | {eventItem.status}</div>
                  <div><strong>{eventItem.subject}</strong></div>
                  <div className="entry-meta">{eventItem.location || "No location"}</div>
                  <div className="row">
                    <button
                      className="button secondary"
                      onClick={(evt) => {
                        evt.stopPropagation();
                        void handleBrief(eventItem);
                      }}
                    >
                      {actionLoading ? "Building..." : "Generate brief"}
                    </button>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="calendar-detail">
            {selectedEvent ? (
              <>
                <div className="entry">
                  <div className="entry-meta">Meeting</div>
                  <div><strong>{selectedEvent.subject}</strong></div>
                  <div className="entry-meta">{new Date(selectedEvent.start_at).toLocaleString()} - {new Date(selectedEvent.end_at).toLocaleString()}</div>
                  <div className="entry-meta">{selectedEvent.location || "No location provided"}</div>
                  <div>{selectedEvent.description || "No description provided."}</div>
                  {selectedEvent.attendees ? (
                    <div className="compact-list">
                      <strong>Attendees</strong>
                      {selectedEvent.attendees
                        .split(",")
                        .map((attendee) => attendee.trim())
                        .filter(Boolean)
                        .slice(0, 8)
                        .map((attendee) => (
                          <div key={attendee}>- {attendee}</div>
                        ))}
                    </div>
                  ) : null}
                </div>

                {meetingBrief && (
                  (meetingBrief.event_id && meetingBrief.event_id === selectedEvent.event_id) ||
                  (!meetingBrief.event_id && meetingBrief.meeting_subject === selectedEvent.subject)
                ) ? (
                  <div className="entry">
                    <div className="entry-meta">Meeting brief</div>
                    <div>{meetingBrief.summary}</div>
                    {meetingBrief.agenda.length ? (
                      <div className="compact-list">
                        <strong>Agenda</strong>
                        {meetingBrief.agenda.map((item, idx) => (
                          <div key={`agenda-${idx}`}>- {item}</div>
                        ))}
                      </div>
                    ) : null}
                    {meetingBrief.decisions.length ? (
                      <div className="compact-list">
                        <strong>Decisions</strong>
                        {meetingBrief.decisions.map((item, idx) => (
                          <div key={`brief-decision-${idx}`}>- {item}</div>
                        ))}
                      </div>
                    ) : null}
                    {meetingBrief.commitments.length ? (
                      <div className="compact-list">
                        <strong>Commitments</strong>
                        {meetingBrief.commitments.map((item, idx) => (
                          <div key={`brief-commitment-${idx}`}>- {item}</div>
                        ))}
                      </div>
                    ) : null}
                    {meetingBrief.risks.length ? (
                      <div className="compact-list">
                        <strong>Risks</strong>
                        {meetingBrief.risks.map((item, idx) => (
                          <div key={`brief-risk-${idx}`}>- {item}</div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </>
            ) : (
              <div className="entry">
                <div className="entry-meta">Select a meeting to open detail.</div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
