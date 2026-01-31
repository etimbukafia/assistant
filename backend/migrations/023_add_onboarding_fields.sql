-- Migration: Add assistant personalization and onboarding fields
-- Description: Adds assistant_name and onboarding_completed to user_settings table

ALTER TABLE user_settings 
ADD COLUMN assistant_name VARCHAR(50) DEFAULT 'Donna';

ALTER TABLE user_settings
ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE;
