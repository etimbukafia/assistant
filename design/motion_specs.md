# Teeks: Motion & Interaction Specs

> *"Animation must have a purpose. It must teach or it must delight. If it does neither, cut it."*

Motion in Teeks is **invisible when working correctly**. The user should not think "nice animation." They should just feel oriented.

---

## 1. Motion Principles

**Motion communicates structure, not aesthetics.**

- Sliding right = going deeper into a stack
- Rising from bottom = modal, temporary, overlaid
- Fading in place = tab switch (lateral, not hierarchical)
- Dropping from top = OmniChat (always accessible, always dismissible)

**Duration is proportional to distance.**
A 4pt micro-shift takes 80ms. A full-screen transition takes 300ms. Never animate a small change slowly — it makes the interface feel broken.

**Easing is always natural.**
Nothing in the physical world moves at constant speed. Use `cubic-bezier` easing. Never `linear` for UI transitions.

**Exits are always faster than entrances.**
The user dismissed something — honour their intent immediately. Entry: 300–320ms. Exit: 180–220ms.

---

## 2. Timing Scale

All values in `Theme.ts` under `Motion`:

| Token | Duration | Curve | Use |
| :--- | :--- | :--- | :--- |
| `Motion.instant` | 80ms | `ease-out` | Colour state changes, hover, focus ring |
| `Motion.fast` | 150ms | `ease-out` | Button press, icon swap, toggle |
| `Motion.standard` | 250ms | `cubic-bezier(0.4, 0, 0.2, 1)` | Card reveal, opacity fade |
| `Motion.enter` | 320ms | Spring: `damping 18, stiffness 90` | Overlay / sheet entrance |
| `Motion.exit` | 200ms | `cubic-bezier(0.4, 0, 1, 1)` | Overlay / sheet dismissal |

---

## 3. Screen Transitions

### Tab Switches
- **Type**: Opacity cross-fade only
- **Duration**: `200ms` `ease-out`
- No sliding. Tabs are lateral — sliding implies hierarchy. A cross-fade implies a context switch.

### Stack Navigation (push/pop)
- **Push (enter)**: Slide in from right `100%→0%`, `300ms`, `cubic-bezier(0.4, 0, 0.2, 1)`
- **Pop (back)**: Slide out to right `0%→100%`, `250ms`, `cubic-bezier(0.4, 0, 1, 1)`
- Simultaneous: outgoing screen slides left at 30% speed of incoming

### OmniChat Overlay (top-down)
- **Enter**: Spring `translateY(-420px → 0)`, `damping: 18`, `stiffness: 90`, `mass: 1.2`
- **Exit**: `translateY(0 → -470px)`, `280ms`, `cubic-bezier(0.4, 0, 1, 1)` (ease-in)
- Backdrop: `opacity` fade `0→0.15`, `250ms` on enter; `200ms` on exit

### Bottom Sheet Modals
- **Enter**: Spring `translateY(100% → 0)`, `damping: 20`, `stiffness: 90`
- **Exit**: `translateY(0 → 100%)`, `220ms`, ease-in
- Drag-to-dismiss: follows finger, snaps closed if velocity > 500pt/s or position > 50%

---

## 4. Component Micro-interactions

### Buttons
- **Press**: `scale(0.97)`, brightness `–5%`, `80ms ease-out`
- **Release**: `scale(1.0)`, `80ms ease-out`
- **Send button only**: `scale(1.0 → 1.08 → 1.0)` on successful send, `150ms`, paired with `impactMedium` haptic

### Session Cards
- **Press**: `translateY(-1px)`, shadow deepens, `80ms ease-out`
- **Release**: `translateY(0)`, `80ms ease-out`
- **Resolved (delete or done)**: `opacity(1 → 0)`, height collapses to 0, `300ms`. Content below fills the gap smoothly.

### Typing Indicator (Assistant thinking)
- Three Peony `#C2185B` dots
- Pulse: `scale(0.8, opacity 0.3) → scale(1, opacity 1)`, `1.2s` cycle
- Stagger: dot 2 starts `+200ms`, dot 3 starts `+400ms`
- **Never use a spinner.** A spinner means the system is struggling. Dots mean thinking is happening.

---

## 5. Loading States

### Skeleton Screens
- Gradient shimmer: `#E4E0D8 → #F5F0E8 → #E4E0D8` diagonal sweep
- Duration: `1.5s`, repeat every `2s`
- Use on: session list cards, message thread on first load

### Brass Sync Line
- A 2pt Brass `#A07850` line progresses across the very top edge of the screen
- Easing: starts slow, accelerates near 80%, completes with a snap
- No percentage number. No label. The line is the communication.

---

## 6. Resolution Animations

### Action Approved — Sage Bloom
- `600ms` radial gradient expands from touch point
- Colour: Sage `#4D7C0F` at `20%` opacity, fades to `0%`
- Simultaneous: action card `opacity 1→0`, height collapses, `300ms`

### Message Sent
- Send button: `scale(1.08)` briefly, then normalises, `150ms`
- Haptic: `impactMedium`
- Bubble animates in from `opacity 0, translateY 8px` → `opacity 1, translateY 0`, `200ms`

### Session Deleted
- Card `opacity 1→0`, height collapses to 0, `250ms`
- Haptic: `notificationWarning` on swipe threshold trigger
- Content below reflows smoothly without a jump

---

> [!IMPORTANT]
> **Reduced motion**: When `UIAccessibility.isReduceMotionEnabled()` is true (iOS) or `prefers-reduced-motion: reduce` (web), all `translateY`, `translateX`, and `scale` animations are removed. Only `opacity` transitions remain, at `150ms`. This is already implemented in `globals.css`. Mobile hooks must check `AccessibilityInfo.isReduceMotionEnabled()` at the component level.
