-- Add category column to contacts table
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS category VARCHAR;
