-- Calendar push notification watch channels
-- Stores active Google Calendar API watch channels per user per calendar.
-- Each channel must be explicitly stopped before renewal (unlike Gmail watch which is idempotent).

CREATE TABLE IF NOT EXISTS calendar_watch_channels (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel_id TEXT NOT NULL UNIQUE,  -- UUID we generate, sent to Google
    resource_id TEXT NOT NULL,        -- Google's resource ID, needed to stop the channel
    calendar_id TEXT NOT NULL,        -- Which calendar this channel watches
    expiration TIMESTAMPTZ NOT NULL,  -- When Google will stop sending notifications
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_calendar_watch_channels_user_id ON calendar_watch_channels(user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_watch_channels_channel_id ON calendar_watch_channels(channel_id);
CREATE INDEX IF NOT EXISTS idx_calendar_watch_channels_expiration ON calendar_watch_channels(expiration);
