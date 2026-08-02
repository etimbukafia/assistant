# EA Diary: Voice Capture Product Spec

## Goal
Add voice as a faster way to capture diary context without creating a separate workflow, object type, or memory model.

Product principle:
`Voice should disappear into Capture Context.`

## Core Product Rules
- voice is an input method, not a separate feature area
- the saved result is still a normal context capture
- scope remains required
- category is still classified asynchronously after save
- voice capture is a `Pro` feature

## Input Pipeline
1. assistant opens `Capture Context`
2. scope is already selected from the current surface, or chosen explicitly
3. assistant taps the mic and records
4. Teeks transcribes with OpenAI speech-to-text (`gpt-4o-mini-transcribe`)
5. if transcript is within the capture limit, save it directly
6. if transcript exceeds the capture limit, shorten it with Gemma
7. save immediately
8. classify asynchronously with Gemma

## Recording Limit
- hard cap: `45 seconds`
- show the timer while recording
- auto-stop at `45s`
- no override
- no extend/continue control

Reason:
- keeps capture focused on one moment
- keeps latency and cost bounded
- prevents voice capture from turning into long-form notes or dictation

## Scope Rules
- scope is required before save
- if capture starts from a contact, email, task, or event surface, that scope should already be selected
- `Global` must still be explicit

## UX States
During recording:
- `Listening...`
- visible timer

After stop:
- `Transcribing...`

After save:
- `Saved`
- `Organizing...`

After classification:
- `Saved as Decision for Sarah`
- `Saved as Insight for Sarah. Teeks was unsure, so it used Insight.`

## Overflow Behavior
If the transcript exceeds the capture text limit:
- compress it with Gemma before save
- save the shortened capture
- keep the UX simple and calm

Optional subtle copy:
- `Teeks shortened this capture for clarity.`

Do not expose:
- model names
- prompt details
- token limits
- transcript confidence

## Privacy Rules
- do not retain raw audio by default
- use audio only for transcription
- delete uploaded audio immediately after transcription returns
- persist only the resulting transcript or shortened capture

If temporary retention is required operationally, it must be short-lived and explicit.

## Non-Goals
- separate `voice note` objects
- transcript review workflow before save
- audio playback/archive UI
- long-form dictation or meeting-note recording

## Success Metrics
- faster capture than typed entry for in-the-moment thoughts
- low abandonment during voice recording
- low correction rate after saved voice captures
- low rate of over-limit recordings

## Jobs-Style Guardrails
- same mental model as typed capture
- no extra workflow complexity
- no surprise recording behavior
- no noisy AI explanation
- one clean saved context entry at the end
