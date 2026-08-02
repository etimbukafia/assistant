# EA Diary: Capture Context Frontend UX Mapping

## Objective
Replace the current typed diary form with a lightweight capture experience that minimizes assistant cognitive load.

## Primary UX Shift
From:
- form-first
- object-type heavy
- documentation feel

To:
- capture-first
- one note field
- required scope
- automatic organization

## Core Screen Changes
### 1. Replace typed diary form with `Capture Context`
New primary UI:
- single multiline input:
  - placeholder: `Capture a moment, decision, risk, preference, or follow-up context...`
- required scope selector
- `Save` action

Remove from primary capture UI:
- manual category picker
- importance selector
- documentation-style field stack

## Scope UX
### 2. Required scope selector
User must choose one:
- `Contact`
- `Email`
- `Task`
- `Event`
- `Global`

Rules:
- if user is on a contact page, preselect that contact
- if user is on an email/task/event surface, preselect that entity
- if there is no ambient context, default to empty and require selection
- `Global` must be chosen intentionally

## Capture Flow
### 3. Save interaction
On save:
1. persist immediately
2. show optimistic saved state
3. classify asynchronously
4. update row/toast when classification returns

Immediate post-save state:
- `Saved`
- temporary category display: `Organizing...`

## Classification Feedback
### 4. Classification result toast/banner
High/medium confidence examples:
- `Saved as Decision for Sarah`
- `Saved as Commitment on Vendor Review thread`

Low-confidence example:
- `Saved as Insight for Sarah. Teeks was unsure, so it used Insight.`

Always show:
- `Change category`

Action-surface rule:
- on email/task/event surfaces, show inline category correction only for the capture created in the current session
- older stored captures should route to the diary/review flow for deliberate editing

## Diary List / Feed Changes
### 5. Simplify list items
Each item should show:
- raw capture text
- resolved category chip
- primary scope label
- subtle uncertainty marker when applicable
- updated time

Do not show:
- excessive metadata
- internal classifier rationale by default
- importance badges or scoring
- historic memory by default on email/task/event surfaces

## Edit Flow
### 6. Inline correction sheet/menu
Users can edit:
- category
- primary scope
- note text
- linked references

Recommended UI:
- kebab menu or inline action on each item
- `Change category`
- `Move to...`
- `Edit text`

Stored memory rule:
- current-session captures can support inline correction in context
- older stored captures on email/task/event surfaces should stay read-only until the user explicitly opens the diary/review flow
- do not make reopening an action surface feel like opening an editor

## Contextual Entry Points
### 7. Add capture entry points where assistants already work
Surfaces:
- contact page
- email/thread view
- task detail
- event/meeting brief screen

Behavior:
- pre-fill scope from current object
- keep the same one-box capture UI everywhere
- on email/task/event surfaces, stored context stays collapsed by default
- revealing stored context must be explicit

## Contact-Centric Behavior
### 8. On contact pages
This should feel like:
- `Add context about Sarah`

After save:
- item appears in Sarah’s context stream immediately
- category updates when classification finishes

## Entity-Centric Behavior
### 9. On email/task/event surfaces
This should feel like:
- `Add context from this email`
- `Add context from this task`
- `Add context from this event`

Teeks may later attach a secondary contact link if confidence is high.

Stored memory rule:
- email/task/event surfaces should show latest stored context as a compact summary first
- full stored content must require explicit reveal
- older stored captures should not become inline-editable just because the panel was reopened

## Global Context UX
### 10. Explicit global path
Use label:
- `Global context`

Do not make this the default.
Use it only when the assistant intentionally wants a non-contact, non-entity note.

## Visual Guidance
### 11. Tone and copy
Avoid knowledge-management language like:
- `Create context entry`
- `Select type`
- `Assign importance`

Prefer:
- `Capture context`
- `Where does this belong?`
- `Teeks will organize it`

## Empty States
### 12. Diary empty state
Use copy like:
- `Capture a moment. Teeks will organize it for you.`

Contact page empty state:
- `Nothing captured for this contact yet. Add context Teeks should remember.`

## Error and Edge States
### 13. Missing scope
Block save with a simple prompt:
- `Choose where this belongs before saving.`

### 14. Classification failure
If async classification fails:
- keep saved note
- keep category as `Insight`
- optionally show:
  - `Saved as Insight. Teeks couldn’t classify it right now.`

## Suggested Frontend Areas Likely To Change
- diary capture composer component
- diary list/feed item component
- contact detail/context section
- thread/message context panel
- task detail context panel
- event/meeting context panel
- toast/notification component for classification result

## Interaction Standard
The assistant should need exactly two deliberate decisions at capture time:
1. what to write
2. where it belongs

Everything else should be automated or editable after save.

Jobs-style guardrails:
- do not auto-reveal stored memory on action surfaces
- do not default to dense history stacks inside email/task/event panels
- keep inline feedback local and calm
- make old memory available, but only after explicit user intent

## Phase Status
### Phase 3
- [x] diary capture surface shows `Organizing...` after save
- [x] diary feed refreshes while captures are pending
- [x] classification feedback lands locally in the diary UX

### Phase 4
- [x] contact page has an inline contextual capture surface
- [x] email/thread view has an inline contextual capture surface
- [x] task detail has an inline contextual capture surface
- [x] event dialog has an inline contextual capture surface
- [x] contextual surfaces reuse the same inline classification/result model
- [x] contact page reveals stored context by default because it is an explicit memory surface
- [x] email/task/event surfaces keep stored context collapsed by default and require explicit reveal
- [x] inline category correction is limited to the current-session capture on email/task/event surfaces

### Next UX Focus
### Phase 5
- [x] show secondary links clearly in the inline contextual capture surfaces
- [x] let assistants remove secondary links without opening the generic diary screen
- [x] distinguish explicit user-added links from Teeks-added links with provenance-backed copy
- [x] defer richer inline history on action surfaces; keep the UX focused on latest context plus explicit reveal

### Phase 6
- [x] diary frontend uses canonical `/context/captures*` routes
- [x] diary contact management uses canonical `/contacts*` routes
- [x] compatibility `/context/entries*` routes are removed
- [x] compatibility `/vault/diary/contacts*` routes are removed
- [x] primary capture UX no longer depends on the old typed-create model
