# Part 6: Backend Engineering Instructions (Jobs-Inspired)

Treat backend engineering as invisible user experience.  
Everything you build must make the product feel faster, calmer, and more trustworthy.

---

## 1. Tie Every Backend Decision to User Experience
- Before building anything, define the user-facing outcome.
- Ask: “What does this help the executive assistant do faster or more confidently?”
- Reject backend work that has no clear UX impact.

---

## 2. Optimize for Speed Relentlessly
- Make common workflows feel instant.
- Prioritize latency over theoretical scalability.
- Use caching, precomputation, and streaming where it improves responsiveness.
- Design for sub-second interactions whenever possible.

---

## 3. Choose Reliability Over Novelty
- Prefer proven, boring infrastructure.
- Avoid experimental architecture in critical paths.
- Build systems that work every time, not systems that look impressive.

---

## 4. Make Systems Deterministic
- Ensure operations are predictable and repeatable.
- Use idempotent APIs wherever possible.
- Eliminate “sometimes it works” behavior.

---

## 5. Design APIs Like Products
- Write APIs that are human-readable and predictable.
- Use clear naming and consistent structures.
- Keep response shapes stable across endpoints.
- Document intent, not just parameters.

---

## 6. Design Graceful Failure Paths
- Assume things will fail and plan for it.
- Implement retries, queues, and fallbacks.
- Never expose raw backend failures to users.
- Fail softly and recover automatically.

---

## 7. Build Observability Into the System
- Log meaningful events, not noise.
- Track real workflows end-to-end.
- Monitor latency, failures, and retries.
- Use metrics to detect friction early.

---

## 8. Treat Privacy as a UX Feature
- Default to least privilege access.
- Minimize stored sensitive data.
- Be explicit about data usage.
- Design systems users can trust instinctively.

---

## 9. Keep Architectures Simple
- Prefer clear flows over clever abstractions.
- Reduce layers and indirection.
- Make systems understandable in a single sitting.
- Complexity must always justify itself.

---

## 10. Practice Backend Craftsmanship
- Write clean, readable code.
- Name things intentionally.
- Refactor aggressively to preserve clarity.
- Build systems that feel inevitable, not accidental.

---

# Part 7: AI Engineering Instructions (Jobs-Inspired)

Build AI that feels calm, trustworthy, and deeply useful.  
AI should feel like quiet intelligence, never chaos.

---

## 1. Use AI Only Where It Reduces Effort
- Add AI only when it removes steps or simplifies decisions.
- Reject AI features that create ambiguity.
- AI must make workflows lighter, not heavier.

---

## 2. Prioritize Clarity Over Cleverness
- Avoid verbose or unpredictable outputs.
- Prefer concise, structured responses.
- Optimize for confidence, not creativity.

---

## 3. Make AI Behavior Predictable
- Use guardrails in critical workflows.
- Constrain outputs where correctness matters.
- Ensure consistent results for similar inputs.
- Eliminate surprising behavior.

---

## 4. Respect User Time
- Deliver fast responses, even if partial.
- Stream results when useful.
- Run heavy AI work asynchronously where possible.
- Responsiveness builds perceived intelligence.

---

## 5. Keep Humans in Control
- Design AI as a co-pilot, not an authority.
- Require confirmation for important actions.
- Provide clear undo paths.
- Ensure users always feel in charge.

---

## 6. Make Decisions Transparent
- Provide short, clear reasoning when helpful.
- Show sources or context for outputs.
- Avoid black-box outcomes in critical flows.
- Clarity builds trust.

---

## 7. Reduce Cognitive Load
- Use AI to summarize, extract, and prioritize.
- Highlight actions, deadlines, and risks.
- Remove noise instead of adding insights.
- Good AI simplifies thinking.

---

## 8. Invest in Context Quality
- Build strong retrieval pipelines.
- Structure memory intentionally.
- Prioritize relevant context over larger models.
- Better context creates smarter AI.

---

## 9. Design Strong Guardrails
- Validate inputs before sending to models.
- Constrain outputs where necessary.
- Implement safety layers and fallbacks.
- Boundaries create confidence.

---

## 10. Make AI Feel Invisible
- Integrate AI into workflows, not separate chat boxes.
- Surface intelligence at the moment of need.
- Avoid making AI the center of attention.
- The best AI feels obvious in hindsight.

---

# Backend + AI Execution Checklist

## Backend
- Does this make real workflows faster?
- Is failure handled gracefully?
- Are APIs clean and predictable?
- Is the system easy to understand?

## AI
- Does this reduce effort or complexity?
- Is the output predictable and trustworthy?
- Does the user remain in control?
- Does this feel calm and reliable?

---

# Operating Principle

Frontend earns attention.  
Backend earns trust.  
AI earns confidence.

Build all three so they feel inevitable.
