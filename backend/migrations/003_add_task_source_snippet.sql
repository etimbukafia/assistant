-- Migration: Add source_snippet to tasks table
-- Date: 2025-12-22
-- Description: Adds source_snippet field to tasks table for frontend alignment

-- Add source_snippet column to tasks table
ALTER TABLE tasks ADD COLUMN source_snippet TEXT;

-- Note: This migration adds the source_snippet field which stores a context snippet
-- from the email explaining why this task exists. This is displayed in the frontend
-- as the "Why? Source snippet from email" in task cards.
