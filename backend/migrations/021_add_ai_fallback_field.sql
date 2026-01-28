-- Add ai_fallback field to messages table
-- Indicates when AI processing failed and fallback/default values were used

ALTER TABLE messages ADD COLUMN IF NOT EXISTS ai_fallback BOOLEAN DEFAULT FALSE;
