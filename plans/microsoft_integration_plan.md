# Microsoft Integration Plan (MVP: Single Provider Only)

## Goal
Mirror the existing Google stack (auth, email, calendar, webhooks, sync, settings, UI) with Microsoft/Outlook support.  
MVP constraint: **a user can connect only one provider at a time (Google *or* Microsoft).**

## MVP Provider Rule
- `UserSettings.connected_provider` = `none | google | microsoft`
- Connect flow must **reject** if another provider is already connected.
- Switching providers requires **disconnect** first.

## Phase 0 — Provider Gating (MVP)
- Add `connected_provider` column to `user_settings`.
- Set `connected_provider = google` on successful Gmail connect.
- Add `/auth/provider/disconnect` to clear provider, stop watches, and remove credentials.
- Settings response includes `connected_provider`.

## Phase 1 — Data Model + Migrations
- Add `OutlookAccount` table mirroring `GmailAccount`.
- Add `provider` fields to `messages` and `calendar_events` (if not already consistent).
- Add indexes/constraints for provider-specific external IDs.

## Phase 2 — Microsoft Auth
- `/auth/microsoft/connect`:
  - Validate provider token via Graph `/me`.
  - Verify required scopes.
  - Store encrypted access/refresh tokens.
  - Set `connected_provider = microsoft`.
  - Create Outlook email + calendar subscriptions.

## Phase 3 — Outlook Email Integration
- `OutlookClient` (Graph API):
  - Get messages, get message detail.
  - Send message / reply.
  - Delta sync (store `last_delta_link` in OutlookAccount).
- `/messages/outlook/sync/initial` and `/messages/outlook/sync/delta`.

## Phase 4 — Outlook Webhooks
- `/webhooks/outlook`:
  - Handle validationToken handshake.
  - Process notifications and trigger delta sync.
- Store subscriptions in `outlook_watch_subscriptions`.
- Add renewal job (similar to Gmail/Calendar renewal).

## Phase 5 — Outlook Calendar
- `MicrosoftCalendarService`:
  - List calendars, availability, create/update/delete events.
  - Sync upcoming events.
  - Setup calendar subscriptions.
- Calendar routes choose provider based on `connected_provider`.

## Phase 6 — Frontend
- Settings: “Connect Google / Connect Microsoft”.
- Disconnect button (required to switch providers).
- Status display uses `connected_provider`.

## Phase 7 — Tests
- Auth: conflict when provider already connected.
- Webhooks: Outlook notification and dedupe.
- Sync: initial + delta.

## Post‑Launch (Dual Provider)
- Remove single-provider guard.
- Allow multiple connected accounts per user.
- Default-provider selection per action (email/calendar).
