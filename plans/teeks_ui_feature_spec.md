# Teeks UI Feature Spec

## Product Thesis
Teeks is `Automation powered by stored context`.

The UI should express two core ideas:
- `Memory`: what Teeks knows
- `Automations`: what Teeks does with that knowledge

Everything else is supporting infrastructure, not the product identity.

## Jobs-Style Product Direction
- Prefer two clear product pillars over a crowded dashboard.
- Do not present Teeks as a generic assistant or workflow builder.
- Do not expose connectors as the starting point.
- Package existing capabilities into a very small set of opinionated automations.
- Keep the UI calm, obvious, and outcome-first.

## Navigation
Top-level navigation should be:
- `Memory`
- `Automations`
- `Settings`

Optional:
- `Inbox` may remain as a work surface, but it should not compete with `Memory` and `Automations` as a top-level product concept.
- `Calendar`, `Tasks`, and `Contacts` should be subordinate work surfaces, not equal product pillars.

## Memory
Purpose:
- Ask memory questions
- Review captures
- Correct memory
- Forget memory

Memory should include:
- `Memory Reflection Space`
- memory review and correction flows
- capture history and vault surfaces

Memory should not feel like records management. It should feel like Teeks remembering, clarifying, and forgetting cleanly.

## Automations
Purpose:
- Turn stored context into ongoing work

The Automations page should be a productized catalog, not a builder UI.

### Automation Catalog v1
1. `Inbox Copilot`
- Triage threads
- Extract tasks
- Draft replies using relationship context and stored memory
- Required connector: Gmail

2. `Meeting Prep`
- Generate meeting briefs
- Pull attendee context
- Surface decisions, commitments, and risks
- Required connector: Calendar
- Optional connector: Gmail for richer prep

### What Is Not an Automation
- `Approval Tracker` is a memory/query feature
- `Executive Memory Capture` is a foundation/input capability
- `Relationship-Aware Drafting` is part of `Inbox Copilot`, not a standalone automation

## Automations Page
Header:
- Title: `Automations powered by your stored context`
- Description: `Turn Teeks memory into ongoing work across your inbox and calendar.`

Each automation card should show:
- name
- one-sentence outcome
- status
- required connectors
- one primary action

Valid statuses:
- `Needs connection`
- `Ready`
- `Running`
- `Drafts only`
- `Off`

Example card:
- `Inbox Copilot`
- `Triage threads, extract tasks, and draft replies using your stored context.`
- `Needs Gmail`
- Primary action: `Set up`

## Automation Detail Pages
Each automation detail page should include:
- `What Teeks will do`
- `Required connections`
- `Safety mode`
- `Memory used`
- `Recent runs`
- `Turn on / Turn off`

### Safety Model
High-trust read automations may run automatically.
Anything outward-facing or risky should remain reviewable until trust is earned.

Examples:
- meeting briefs: automatic
- drafts: reviewable
- external sends: not automatic by default

## Connector Model
Connectors should appear inside automation setup, not as their own first-class product.

Preferred flow:
1. User picks an automation
2. Teeks explains what connection is needed
3. User connects the required account
4. Automation is activated with minimal settings

Do not make users build workflows from connectors.

## Design Principles
- Outcome-first, not plumbing-first
- Fewer primary choices
- Strong product hierarchy
- One primary action per card
- Calm system states
- No automation marketplace sprawl

## Implementation Guidance
- Reframe current chat/vault under `Memory`
- Introduce a new `Automations` top-level page
- Launch with only `Inbox Copilot` and `Meeting Prep`
- Treat inbox drafting, task extraction, attendee context, and briefing assembly as internal capabilities inside those automations
