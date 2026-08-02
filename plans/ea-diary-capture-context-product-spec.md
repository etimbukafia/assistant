# EA Diary: Capture Context Product Spec

## Goal
Replace the current typed EA diary workflow with a lightweight capture flow:
- assistants capture a moment quickly
- Teeks classifies and organizes it automatically

The product principle is:
`Assistants capture moments. Teeks organizes them.`

## Core Model
Three building blocks remain:
1. `Contacts`
2. `Context`
3. `Entities`
   - `email`
   - `task`
   - `event`

## Capture Experience
New diary UX:
1. assistant writes a note
2. assistant chooses where it belongs
   - contact
   - email
   - task
   - event
   - global
3. assistant saves immediately
4. Teeks classifies it asynchronously

Example:
`Sarah approved vendor X for Q3 expansion`

Result:
- scope: `contact: Sarah`
- category: `decision`

## Scope Rules
- Scope is required before save.
- `global` must be explicit, not accidental fallback.
- If the user is already inside a contact/thread/event/task surface, Teeks should preselect that scope.

## Categories
Allowed categories:
- `decision`
- `risk`
- `commitment`
- `preference`
- `insight`

Out of scope for now:
- `relationship`
- `importance`

## Classification Rules
- Teeks classifies every saved capture using Gemma asynchronously.
- If confidence is high or medium, assign the detected category.
- If confidence is low, default to `insight`.
- Original captured text is always preserved.

## Confidence + User Feedback
After classification, show a lightweight confirmation:
- `Saved as Decision for Sarah`
- `Saved as Insight for Sarah. Teeks was unsure, so it used Insight.`

Always offer:
- `Change category`

Low-confidence captures should be visibly but subtly marked as uncertain. Do not create a noisy review queue by default.

## Linking Rules
- User-selected scope is the primary scope.
- Teeks may add secondary links when confidence is high, especially:
  - entity -> contact
  - contact -> related email/task/event
- Secondary linking must be quiet, editable, and must never block save.

## Editing
Users can change:
- category
- primary scope
- linked entities/contacts
- raw text

System should retain:
- original classification
- current category
- confidence
- whether the user corrected it

## Backend Shape
Each capture should store:
- `raw_text`
- `primary_scope_type`
- `primary_scope_id`
- `category`
- `classification_confidence`
- `classification_status`
- `secondary_links`
- `user_corrected`
- timestamps

## Success Metrics
- faster time-to-save
- more diary usage
- lower abandonment during capture
- low manual recategorization rate
- more contact-linked context captured

## Non-Goals
- forcing assistants to choose category during capture
- importance scoring
- relationship category
- blocking save while secondary links are inferred
