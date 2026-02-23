# Teeks: Design & Engineering Principles

> *"Simple can be harder than complex. You have to work hard to get your thinking clean to make it simple."*
> — Steve Jobs

These are not guidelines. They are the convictions that every design and engineering decision must pass through. If a decision contradicts one of these principles, the decision is probably wrong.

---

## Part 1: The User

Everything begins here. Get this wrong and nothing else matters.

**Executive Assistants are power users under pressure.**

They are not leisurely browsing. They are managing a high-stakes professional environment with dozens of open threads, competing deadlines, and a principal who expects things to just be handled. They have no patience for a tool that needs to be learned, configured, or explained.

**What they need to feel:**
- **In control** — the tool is working *for* them, not creating more work
- **Ahead** — they are 15 minutes ahead of the problem, not reacting to it
- **Trusted** — the tool never does anything without their explicit approval

**What will make them abandon the product in 30 seconds:**
- A multi-step onboarding flow
- A loading screen with no indication of progress
- An AI response that is wrong, generic, or longer than necessary
- Anything that feels like it was designed for a 22-year-old's task list

---

## Part 2: Design Principles

### 1. One thing per screen
Every screen has one primary goal. One. If a screen has two equal-weight actions, one of them is on the wrong screen. The EA must be able to glance at a screen and know immediately what it wants them to do.

*In Teeks:* The chat session screen wants one thing — for the EA to send a message or approve an action. Not both simultaneously.

### 2. The best interface is no interface
Every tap the user doesn't have to make is a gift. Every word they don't have to read is respect for their time. When Teeks has already prepared the draft, it shows the draft — not a prompt asking if the EA would like to see a draft.

*Ask before adding any UI element:* "What does the user have to do now that they wouldn't have had to do without this?" If the answer is "nothing useful," cut it.

### 3. Earn trust, then act
Teeks never takes irreversible action without explicit approval. Draft a reply — yes. Send it — only with a deliberate tap on a clearly-labelled "Send" button. The EA's professional reputation depends on this. One wrong email sent automatically destroys the relationship with the product permanently.

*The confirmation must be obvious:* Colour, label, and position must all communicate "this will actually do something." Peony `#C2185B` is the trust signal. When the EA sees Peony, they know: this button does the thing.

### 4. Prepare, don't prompt
The difference between Teeks and a generic AI tool is whether it presents work or asks for work. When an email needs a reply, Teeks surfaces a draft. When a meeting needs a briefing, Teeks has the context ready. The EA approves or adjusts. They do not initiate.

### 5. Consistency is respect
When a component behaves one way on screen A, it behaves the same way on screen B. Every inconsistency forces the EA to spend cognitive energy re-learning. That energy is not theirs to give — they need it for their actual job. Design systems exist precisely to prevent each screen from reinventing what a button looks like.

### 6. Craft the details nobody notices
The spacing between a timestamp and the message above it. The precise weight of a hairline border. The milliseconds it takes for a card to lift on press. Nobody will consciously notice these things when they are right. Everyone will feel something is wrong if they are not. This is the work that separates a professional tool from a prototype.

### 7. Error states are design problems
If the user encounters an error, the interface must tell them exactly what happened and exactly what to do next. "Something went wrong" is not an error message — it is an admission that nobody thought about this moment. Every error state was foreseeable. Design it.

---

## Part 3: Engineering Principles

### 1. Performance is a design decision
If the user has to wait, they are thinking about waiting instead of their work. Perceived performance matters as much as actual performance. Skeleton screens, instant optimistic updates, and pre-fetching are not optional polish — they are design requirements.

*Target*: Any primary action (sending a message, opening a session) must feel instantaneous. If it takes longer than 300ms, add a spinner immediately rather than leaving a frozen screen.

### 2. Tokens, not hardcoded values
No colour, spacing, radius, or font size is ever written as a raw value in a component. Everything references the design token system in `Theme.ts` (mobile) or `globals.css` (web). This is how the design system propagates changes — if a value is hardcoded, the next palette change creates debt.

### 3. Code reflects the design's intent
A component should make the design intent obvious to the next engineer reading it. Component names, prop names, and comment placement should explain *why*, not just *what*. If a magic number appears in the code, there should be a comment next to it explaining it.

### 4. States are not afterthoughts
Empty state, loading state, error state, partial state — these are not edge cases. They are the moments when the EA is most likely to lose trust in the product. They must be designed with the same care as the "happy path."

### 5. Accessibility is not a phase
WCAG AA is implemented during build, not audited afterward. Focus rings, touch targets, VoiceOver labels, and reduced motion support are written alongside the component, not added in a follow-up sprint.

---

## Part 4: The Daily Test

Before any design or code goes to review, ask:

1. **Does this screen have one clear primary action?**
2. **Could the EA complete this in under 10 seconds?**
3. **Is every colour coming from a design token?**
4. **Does Peony appear more than once on this screen?** (It should not.)
5. **What happens when this fails?** Is the error state designed?
6. **Does this feel inevitable?** — the best designs feel like they were the only possible choice.

If any of these fail, the work is not done.

---

> [!IMPORTANT]
> **The Product Test**: Once a week, use Teeks to actually help with something. Not to test it — to use it. The moment it feels like software to be operated rather than a tool that helps, something has gone wrong. Find it.