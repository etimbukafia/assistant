# Teeks: Component States & Interaction Guide

Every state a component can be in must be **deliberate**. Not "what happens when the user does X" — but "what should the user *feel* when this happens."

---

## 🔘 1. Buttons

### Primary Button (Peony)

| State | Visual | Haptic |
| :--- | :--- | :--- |
| **Default** | Background `#C2185B`, white label, `border-radius: 8pt` | — |
| **Pressed** | Scale `0.97`, brightness `–5%`, shadow compresses | `impactMedium` ("tock") |
| **Hover (web)** | `brightness(1.08)`, `cursor: pointer` | — |
| **Loading** | Label hidden, white spinner centered, background stays Peony | — |
| **Disabled** | Background `#C2185B` at `35%` opacity, not greyscale | — |

**Rule:** The disabled state keeps the Peony colour at low opacity — it tells the user *what will happen when it activates*, not that the button is broken.

### Secondary Button (Outlined)

| State | Visual | Haptic |
| :--- | :--- | :--- |
| **Default** | White background, `1pt #E4E0D8` border, Ink Black label | — |
| **Pressed** | Background `#F5F0E8`, border `#CCC8BF` | `impactLight` |
| **Hover (web)** | Border `#CCC8BF`, subtle shadow | — |
| **Disabled** | All at `40%` opacity | — |

### Destructive Button (Ghost / Carmine)

| State | Visual | Haptic |
| :--- | :--- | :--- |
| **Default** | Transparent, Stone label | — |
| **Pressed** | Carmine `#9B1C1C` label, faint Carmine background | `notificationWarning` |
| **Confirm required** | Two-tap pattern — first tap reveals a "Are you sure?" confirmation inline | — |

---

## ⌨️ 2. Inputs & Text Areas

| State | Border | Background | Notes |
| :--- | :--- | :--- | :--- |
| **Empty** | `#E4E0D8` | `#F5F0E8` Ivory | Placeholder in Mist `#A1A1AA` |
| **Focused** | `#C2185B` Peony, 1pt | `#FFFFFF` White | The Peony focus moment |
| **Filled** | `#E4E0D8` | `#FFFFFF` White | Ink Black text |
| **Error** | `#9B1C1C` Carmine, 1pt | `#FFFFFF` | Shake animation (3px, 180ms), error message below |
| **Disabled** | `#E4E0D8` | `#F5F0E8` at `60%` | No interaction, cursor `not-allowed` |

**Error message copy rule**: State the problem and the fix. "Email required." not "This field cannot be empty."

---

## 📇 3. Session Cards

| Type | Left border | Icon | Behaviour |
| :--- | :--- | :--- | :--- |
| **Standard Action** | None | Brass `#A07850` lightning | Tap to open session |
| **Standard Reflection** | None | Sage `#4D7C0F` leaf | Tap to open, marked ephemeral |
| **Urgent** | 3pt Carmine `#9B1C1C` | Carmine alert circle | Sorted to top of list |
| **Resolved** | None | Sage checkmark | Fades to `60%` opacity, strike-through title |

**Press state (all cards):**
- `translateY(-1px)`, shadow deepens to `0 4px 16px rgba(0,0,0,0.09)`
- Duration: `80ms` ease-out
- Communicates physicality — the card *lifts*

**Swipe-to-delete (mobile):**
- Reveal Carmine `#9B1C1C` delete zone from right
- Requires deliberate swipe past `60%` to confirm — prevents accidents
- Haptic: `notificationWarning` on trigger threshold

---

## 💬 4. Message Bubbles

| Type | Background | Text | Radius detail |
| :--- | :--- | :--- | :--- |
| **User** | Peony `#C2185B` | White | `border-bottom-right-radius: 4pt` — the send corner collapses |
| **Assistant** | White `#FFFFFF`, `1pt #E4E0D8` border | Ink Black | `border-bottom-left-radius: 4pt` |
| **Error** | White, `1pt #9B1C1C` border | Carmine text | Retry link inline |
| **Processing** | White | — | Three Peony dots, staggered 200ms pulse |

---

## 🧭 5. Navigation

### Bottom Tab Bar

| State | Icon | Label | Indicator |
| :--- | :--- | :--- | :--- |
| **Active** | Peony `#C2185B` stroke | Peony label | — |
| **Inactive** | Stone `#71717A` stroke | Stone label | — |
| **Badge** | — | — | Small Carmine dot, 6pt diameter, top-right of icon |

Tab switches use `opacity` cross-fade only — `200ms`. No sliding. Sliding implies direction; tabs are lateral, not hierarchical.

### Headers

- Title: Playfair Display, 22pt, Ink Black, left-aligned
- Back button: `chevron-left` in Stone, tappable area 48×48pt minimum
- Right actions: Stone icon, becomes Peony on active state

---

## 🌀 6. Global Feedback States

### Progress — Brass Sync Line
During inbox sync or AI processing: a thin Brass `#A07850` line progresses across the very top of the screen. 2pt height. No percentage number. The line says "work is happening." That is enough.

### Action Confirmation — Sage Bloom
When the user approves an action card: a brief radial gradient expands from the point of touch in Sage `#4D7C0F`, `200ms`, then fades. Subtle. Not a celebration — a confirmation.

### Error Feedback — Carmine Shake
On failed submission or error: the relevant element shakes `3px` left-right, `3` times, `60ms` per oscillation. Carmine border appears simultaneously. No modal. No alert. Inline, immediate.

---

> [!NOTE]
> **Token rule**: No colour value is ever hardcoded in a component file. All states reference `Colors.*` from `Theme.ts` (mobile) or `hsl(var(--*))` from `globals.css` (web). If you are typing a hex value in a component, stop and use the token.
