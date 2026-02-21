-- Structured memory tables for chat/diary integration.
-- Adds context_entries, contacts, and entity_references.

CREATE TABLE IF NOT EXISTS context_entries (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    content TEXT NOT NULL,
    entity_type VARCHAR NOT NULL,
    entity_id VARCHAR,
    created_by VARCHAR NOT NULL DEFAULT 'You',
    importance_level VARCHAR NOT NULL DEFAULT 'normal',
    status VARCHAR NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_context_entries_type CHECK (type IN ('decision','commitment','preferences','insight','relationships')),
    CONSTRAINT ck_context_entries_entity_type CHECK (entity_type IN ('assistant','contact','thread','message','event','executive')),
    CONSTRAINT ck_context_entries_created_by CHECK (created_by IN ('Teeks','You')),
    CONSTRAINT ck_context_entries_importance_level CHECK (importance_level IN ('low','normal','high')),
    CONSTRAINT ck_context_entries_status CHECK (status IN ('active','resolved','stale','archived'))
);

CREATE INDEX IF NOT EXISTS ix_context_entries_user_id ON context_entries(user_id);
CREATE INDEX IF NOT EXISTS ix_context_entries_entity_type ON context_entries(entity_type);
CREATE INDEX IF NOT EXISTS ix_context_entries_entity_id ON context_entries(entity_id);
CREATE INDEX IF NOT EXISTS ix_context_entries_type ON context_entries(type);
CREATE INDEX IF NOT EXISTS ix_context_entries_status ON context_entries(status);
CREATE INDEX IF NOT EXISTS ix_context_entries_created_at ON context_entries(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_context_entries_expires_at ON context_entries(expires_at);
CREATE INDEX IF NOT EXISTS ix_context_entries_user_entity ON context_entries(user_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_context_entries_user_type ON context_entries(user_id, type);

CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    email VARCHAR,
    role VARCHAR,
    organization VARCHAR,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_contacts_user_id ON contacts(user_id);
CREATE INDEX IF NOT EXISTS ix_contacts_name ON contacts(name);
CREATE INDEX IF NOT EXISTS ix_contacts_email ON contacts(email);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_contacts_user_email'
    ) THEN
        ALTER TABLE contacts
            ADD CONSTRAINT uq_contacts_user_email UNIQUE (user_id, email);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS entity_references (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    entity_type VARCHAR NOT NULL,
    display_name VARCHAR NOT NULL,
    ref VARCHAR NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_entity_references_type CHECK (entity_type IN ('thread','message','event'))
);

CREATE INDEX IF NOT EXISTS ix_entity_references_user_id ON entity_references(user_id);
CREATE INDEX IF NOT EXISTS ix_entity_references_entity_type ON entity_references(entity_type);
CREATE INDEX IF NOT EXISTS ix_entity_references_display_name ON entity_references(display_name);
CREATE INDEX IF NOT EXISTS ix_entity_references_ref ON entity_references(ref);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_entity_refs_user_type_name'
    ) THEN
        ALTER TABLE entity_references
            ADD CONSTRAINT uq_entity_refs_user_type_name UNIQUE (user_id, entity_type, display_name);
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_entity_refs_user_type_ref'
    ) THEN
        ALTER TABLE entity_references
            ADD CONSTRAINT uq_entity_refs_user_type_ref UNIQUE (user_id, entity_type, ref);
    END IF;
END
$$;
