# Donna: Interactive Prototype Plan (Demo Mode)

This document outlines the flows for a high-fidelity "Demo Mode" designed to simulate real-world usage and validate the Donna experience.

---

## 🎯 1. Prototype Objectives
- **Zero-Data Utility**: Show the app's value before Gmail is actually connected.
- **Critical Path Validation**: Ensure the "One-Tap" resolution feels as fast in practice as it does in theory.
- **Motion Verification**: Test the transitions (e.g., "The Bloom") at 60fps.

---

## 🗺️ 2. Core Clickable Flows

### Flow A: The "First Briefing" (Onboarding)
*   **Path**: Landing -> Connect -> Syncing Animation -> First Dashboard.
*   **Interactive Steps**:
    1.  Tap `[Connect Gmail]`.
    2.  Watch the "Cerulean Orbit" sync animation (3 seconds).
    3.  Enter the Dashboard and see the specific demo message: *"I've analyzed your desk; 3 high-priority items await."*

### Flow B: The "Morning Reschedule" (Intelligence)
*   **Path**: Dashboard Card -> Detail View -> Suggest Selection -> Confirmation.
*   **Interactive Steps**:
    1.  Tap the `[Board Meeting Conflict]` card.
    2.  In Detail View, tap `[Suggest Times]`.
    3.  Select two "Cerulean" slots.
    4.  Tap `[Send Options]`.
    5.  Watch the "Handled" bloom effect as the card resolves.

### Flow C: The "Focus Hub" Handover (Closure)
*   **Path**: Inbox -> Focus Tab -> Mark Done.
*   **Interactive Steps**:
    1.  Navigate to `[Focus]` tab.
    2.  Identify the `[Prep Q4 Budget]` task.
    3.  Toggle the checkbox.
    4.  Observe the "Green Bloom" and content re-flow.

---

## 🛠️ 3. "Demo Mode" Technical Setup

### Static Data Injection
Instead of calling the real backend modules, the prototype will use a `demo_state.json`:
- **Messages**: 5 curated threads (Urgent, FYI, Personal).
- **Tasks**: 3 placeholder tasks with varying priorities.
- **Schedule**: A fixed "Conflict Day" (Jan 12th).

### Interaction Constraints
- Any button outside the core flows triggers a "Restricted in Demo Mode" Cerulean toast.
- The "Donna Pulse" FAB allows switching between Flow A, B, and C for quick testing.

---

## 🧪 4. UX Validation Metrics
- **TPS (Taps Per Success)**: Each core flow should require no more than 3-4 taps.
- **Transition Smoothness**: Zero "jank" during shared element expansions.
- **Brand Recall**: Does the "Donna Paulsen" vibe translate through the persona-driven copy?

---

> [!TIP]
> **Implementation**: Use a separate `demo` environment variable to toggle this mode in the frontend. Reference the `design_system.md` for consistent styling of demo-only elements.
