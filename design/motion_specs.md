# Donna: Motion & Interaction Specs

Motion in Donna is **Sleek, Intentional, and High-Performance**. It should feel like a well-tailored suit—smooth where it counts and sharp when it responds.

---

## 🏎️ 1. Motion Principles

- **No "Bouncing"**: Avoid playful or bouncy easing. Use smooth, professional curves.
- **Intentional Delay**: If a transition includes AI processing, give it a subtle 300ms "breath" to imply meaningful work.
- **Hierarchy-Driven**: The most important data appears first (e.g., the Summary snippet fades in 100ms before the detail tags).

---

## 📐 2. Animation Curves & Timing

| Action Type | Duration | Easing (CSS/RN) | Description |
| :--- | :--- | :--- | :--- |
| **Standard Entry** | 300ms | `cubic-bezier(0.4, 0, 0.2, 1)` | Cards sliding into the feed. |
| **Micro-interaction**| 150ms | `ease-out` | Button presses, toggle switches. |
| **Deep Transition** | 450ms | `cubic-bezier(0.2, 0, 0, 1)` | Shared element expansion (Card to Detail). |
| **Feedback Hint** | 600ms | `linear` | The "Cerulean Sync" progress bar. |

---

## 📑 3. Screen Transitions

### A. Persistent Navigation (Tabs)
- **Visual**: Simple cross-fade (0ms duration on icons, 200ms on screen content).
- **Behavior**: Content fades out from `opacity: 1` to `0.8` while sliding slightly (8px) to the left to emphasize progress.

### B. Detail Expansion (Common Flow)
- **Visual**: The card background expands to fill the screen while the `Summary` text remains fixed or slides into its new header position.
- **Depth**: Elements behind the card blur (`20px`) during the first 150ms of the transition.

---

## 🔘 4. Micro-Interactions

### The "One-Tap" Feedback
- **Press State**: Subtle 2% scale-down with a concurrent `overlay: rgba(255,255,255,0.05)`.
- **Haptics**: 
  - **Success**: Soft double-tap.
  - **Urgent/Error**: Sharp single-tap with longer vibration.

### Choice Selection (Cerulean Selector)
- When selecting a scheduling slot, the card border color sweeps from `color-border` to `accent-cerulean` in a clockwise circular motion.

---

## 🌀 5. Loading & Syncing States

### The "Cerulean Orbit"
- **Logic**: A 12px Cerulean dot orbits a central Obsidian core. 
- **Rotation**: Starts slow (1s per rev), accelerates as processing nears completion.

### The Shimmer (Dashboard)
- **Visual**: Diagonal sweep of light (`color-bg-elevated` to `color-bg-base`) across skeleton cards.
- **Timing**: 1.5s duration, repeating every 2s.

---

## 🛠️ 6. Dismissal & Resolution

### The "Handled" Bloom
- When a task is marked [Done], the card's `accent-red` border turns `green` for 200ms, then a "Bloom" (circular fade-out) expands from the checkmark until the card is invisible. 
- Content below slides up to fill the gap smoothly over 300ms.

---

> [!NOTE]
> **Implementation**: For React Native, use `Reanimated 3` for shared element transitions. For CSS, utilize `transition` properties with the specified cubic-beziers. 
