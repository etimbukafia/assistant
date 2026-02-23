# Teeks Design System

> *"Design is not just what it looks like and feels like. Design is how it works."*
> — Steve Jobs

This is not a style guide. It is a set of **convictions** about how Teeks should feel in the hand of an executive assistant who is moving fast, under pressure, and trusts this tool with their professional life.

---

## Philosophy First

Every decision in this document flows from three beliefs:

1. **One thing at a time.** An EA's attention is their most valuable asset. Teeks never competes with itself on screen. One primary action. One primary colour. One clear next step.

2. **Earned, not explained.** Teeks should feel immediately familiar. No tooltips. No onboarding carousels. If a feature needs explaining, the feature is wrong.

3. **The tool disappears.** The best interface is the one the user stops noticing. Teeks should feel less like software and more like muscle memory.

---

## 🎨 1. Colour — The Permanent Ink Palette

Colour is the first thing remembered. Use it like a decision, not a decoration.

### The Rule
Peony appears **once per screen**. On the primary action. Nowhere else.

### Palette

| Token | Hex | HSL | Role |
| :--- | :--- | :--- | :--- |
| `color-bg-base` | `#F5F0E8` | `38 30% 92%` | Primary background — Ivory Paper |
| `color-bg-surface` | `#FFFFFF` | `0 0% 100%` | Card, sheet, modal surface |
| `color-accent-peony` | `#C2185B` | `336 68% 44%` | **The moment.** Primary CTA, send button, active state |
| `color-accent-brass` | `#A07850` | `30 26% 47%` | Action mode icon, secondary interactive |
| `color-accent-sage` | `#4D7C0F` | `89 73% 27%` | Reflection mode, success states |
| `color-accent-slate` | `#334155` | `213 35% 26%` | Precision links, informational |
| `color-text-primary` | `#18181B` | `240 4% 10%` | Body copy, titles — Ink Black |
| `color-text-secondary` | `#71717A` | `240 4% 46%` | Metadata, labels — Stone |
| `color-text-muted` | `#A1A1AA` | `240 5% 65%` | Placeholders, disabled |
| `color-border` | `#E4E0D8` | `38 16% 86%` | Hairline dividers |
| `color-border-strong` | `#CCC8BF` | `38 11% 77%` | Focused inputs, separators |
| `color-urgent` | `#9B1C1C` | `0 50% 35%` | Carmine — urgent items, errors |

### Colour Pairing Rules
- **Peony + Ink Black** = primary surfaces. Confident. Use on CTA buttons.
- **Peony + Ivory** = never. Too little contrast. Fails WCAG.
- **Brass + Ivory** = Action mode cards, session icons. Warm, professional.
- **Sage + Ivory** = Reflection mode. Calm, considered.
- **Carmine + White** = Urgent only. Never decorative.

---

## 🖋️ 2. Typography

Type is the core of the product. An EA reads and writes for a living. Every font decision must honour that.

### Typefaces
- **Playfair Display** — Display only. Headlines, logo, screen titles. The serif creates authority and warmth. Never use below 20px.
- **Inter** — Everything else. Chosen for its legibility at small sizes and neutral professionalism. No other sans-serif.

### Scale

| Style | Typeface | Size | Weight | Line Height | Tracking | Use |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Display** | Playfair | 36pt | 600 | 44pt | -0.02em | Hero moments only |
| **H1** | Playfair | 28pt | 600 | 34pt | -0.02em | Screen titles |
| **H2** | Playfair | 22pt | 600 | 28pt | -0.01em | Section headings |
| **Body Large** | Inter | 17pt | 400 | 26pt | 0 | Cards, primary content |
| **Body** | Inter | 15pt | 400 | 22pt | 0 | Chat, messages |
| **Label** | Inter | 13pt | 500 | 20pt | 0 | Buttons, tags |
| **Caption** | Inter | 12pt | 400 | 18pt | 0 | Metadata, timestamps |
| **Overline** | Inter | 11pt | 700 | 16pt | +1.2px (caps) | Section markers, mode pills |

### Typography Rules
- **Headlines left-aligned.** Always. Centred headlines are for greeting cards.
- **Body text max-width: 680px** on web. Discomfort begins after 80 characters per line.
- **Never use font-weight 300.** It disappears on non-retina screens. The minimum is 400.
- **Line height is not optional.** Body text without breathing room communicates urgency. Body text with it communicates calm. Teeks should feel calm.

---

## 📐 3. Spacing & Layout

> *"White space is not empty space. It is breathing room. It is the pause before the important word."*

### Grid
- **Mobile**: 4-column, 20pt margins, 16pt gutters
- **Web**: 12-column, 40pt margins, 24pt gutters
- **Max content width (web)**: 1280px

### Spacing Scale (Base 4pt)

| Token | Value | Use |
| :--- | :--- | :--- |
| `xs` | 4pt | Icon padding, dot spacing |
| `sm` | 8pt | Internal component gaps |
| `md` | 16pt | Standard gutter, card padding |
| `lg` | 24pt | Between sections |
| `xl` | 32pt | Page-level vertical rhythm |
| `xxl` | 48pt | Hero sections, screen-level breathing |

### Density Rule
Teeks is a **medium-density** interface. Not the compressed density of Bloomberg Terminal. Not the airy emptiness of a meditation app. An executive's work is dense — the interface should feel serious without being suffocating.

---

## 🔘 4. Radius

Radius communicates personality. Teeks is not bubbly and it is not sharp. It is **considered**.

| Token | Value | Use |
| :--- | :--- | :--- |
| `radius-xs` | 4pt | Pill tags, micro badges |
| `radius-component` | 8pt | Buttons, inputs, chips |
| `radius-surface` | 14pt | Cards, sheets, overlays |
| `radius-full` | 999pt | Avatars, icon containers, mode pills |

**Rule:** Never mix radius values within the same component family. A card and its child button must share a radius logic.

---

## 📦 5. Components

### Buttons

| Variant | Background | Text | Use |
| :--- | :--- | :--- | :--- |
| **Primary** | Peony `#C2185B` | White | The one thing we want the user to do |
| **Secondary** | White, Peony border | Peony | Acceptable alternative action |
| **Ghost** | Transparent | Stone | Destructive or low-priority actions |
| **Urgent** | Carmine `#9B1C1C` | White | Delete, cancel subscription |

**Button rules:**
- One primary button per screen. One. If you have two, you haven't made a decision.
- Full-width primary buttons on mobile. Partial-width feels like an afterthought.
- Minimum touch target: 48×48pt. Human fingers are not pixel-precise.
- Haptic feedback is **required** on every tap on iOS. "Tock" (impact medium) on primary actions. "Tick" (impact light) on secondary.

### Cards — The Teeks Card

The card is the primary unit of information. Everything important is a card.

- **Padding**: 16pt all sides
- **Radius**: 14pt
- **Border**: 1pt `#E4E0D8`
- **Shadow**: `0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)`
- **Background**: `#FFFFFF`

**Card states:**
- **Standard**: White background, hairline border
- **Urgent**: 3pt Carmine left border — `#9B1C1C`. Used sparingly. If everything is urgent, nothing is.
- **Informational**: 3pt Deep Slate left border — `#334155`
- **Active/Selected**: Peony 8% background tint (`#C2185B14`), 1pt Peony border

### Session Icons

Icon containers carry the mode personality visually. Never use arbitrary colours.

- **Action session**: Brass tint background (`#A0785014`), Brass icon
- **Reflection session**: Sage tint background (`#4D7C0F18`), Sage icon
- **Urgent session**: Carmine tint background (`#9B1C1C14`), Carmine icon

### Message Bubbles

- **User bubble**: Peony `#C2185B`, white text, `border-bottom-right-radius: 4pt` (the send corner collapses, like a folded note)
- **Assistant bubble**: White, Ink Black text, hairline border, `border-bottom-left-radius: 4pt`
- **Max width**: 80% of container
- **Padding**: 10pt vertical, 14pt horizontal

### Inputs

- **Background**: Ivory `#F5F0E8`
- **Border (default)**: `#E4E0D8`
- **Border (focused)**: Peony `#C2185B`, 1pt — the focus moment is the Peony moment
- **Placeholder**: Mist `#A1A1AA`
- **Text**: Ink Black `#18181B`, Inter 15pt
- **Radius**: 12pt

---

## ✨ 6. Motion & Animation

> *"Animation must have a purpose. It must teach or it must delight. If it does neither, cut it."*

### Principles
- **Motion communicates structure**, not just decoration. Sliding in from the right means "I went deeper." Sliding from the bottom means "this is overlaid, not navigated to."
- **Duration is a function of distance.** Short movement = short duration. Don't slow-motion a 4pt shift.
- **Easing is always ease-in-out (cubic-bezier).** Never linear. Nothing in the physical world moves at constant speed.

### Timing Scale

| Token | Duration | Use |
| :--- | :--- | :--- |
| `motion-instant` | 80ms | Colour state changes (hover, focus) |
| `motion-fast` | 150ms | Button feedback, icon transitions |
| `motion-standard` | 250ms | Card reveal, opacity fade |
| `motion-enter` | 320ms | Sheet/overlay slide-in |
| `motion-exit` | 200ms | Sheet/overlay close (exits should always be faster than entrances) |

### Specific Behaviours
- **OmniChat overlay**: Springs in from top with damping 18, stiffness 90. Not a linear slide — it should feel like it *drops* into place.
- **Send button**: Scale 1→1.06 on press, back to 1 on release. 80ms. Like pressing a physical key.
- **Session card on press**: `translateY(-1px)`, shadow deepens. Communicates physicality — the card lifts.
- **Typing indicator**: Three-dot pulse, staggered 200ms. Never a spinner — a spinner means the system is struggling. Dots mean the assistant is thinking.

---

## 🔊 7. Haptics (iOS)

Haptics are the one channel the user doesn't look at. Use them to confirm, not to startle.

| Event | Haptic type |
| :--- | :--- |
| Send message | `impactMedium` ("tock") |
| Approve action card | `impactHeavy` ("thud") — consequence confirmed |
| Dismiss action card | `impactLight` |
| Delete session | `notificationWarning` |
| Long press / mode switch | `impactMedium` |
| Error | `notificationError` |

---

## 🗣️ 8. Voice & Tone of UI Copy

The interface speaks. Every label, placeholder, and empty state is a sentence the product says to a professional. It must sound like a sharp, discreet colleague — not a chatbot.

### Rules
- **No exclamation marks.** Ever. Excitement is not our register.
- **No jargon.** "Session" is fine. "Omnichannel context layer" is not.
- **Active voice.** "Send reply" not "Reply will be sent."
- **Brief placeholders.** The placeholder is a whisper. `Ask Teeks?` not `Tell Teeks what you'd like to accomplish today!`
- **Error messages are honest.** "That didn't send. Try again." not "Oops! Something went wrong."

### Empty States copy rule
An empty state is an invitation, not an apology. Write it as one line that describes what's possible, and one CTA that makes it happen. No more.

> ❌ "No conversations yet. Start a chat to get help with your tasks, reflect on your day, or organize your inbox!"
>
> ✅ "Your conversations appear here." → **Start a chat**

---

## 🚨 9. Urgent Treatment

Urgency is rare. When overused, it becomes noise.

- **1 urgent item** in a list: Red left-border card. Eyes go to it.
- **2-3 urgent items**: Same. Still readable.
- **4+ urgent items**: The system is wrong. Something upstream has over-flagged. Do not make 4 cards all red — that's the same as making 0 cards red.

The Carmine `#9B1C1C` is reserved exclusively for:
- Time-critical items (meeting in < 30 minutes)
- Failed actions (send failed, sync error)
- Destructive confirmation buttons

---

## ♿ 10. Accessibility

These are not optional.

| Requirement | Standard |
| :--- | :--- |
| Text contrast (body) | ≥ 4.5:1 (WCAG AA) |
| Text contrast (large / UI) | ≥ 3:1 |
| Touch targets | ≥ 48×48pt |
| Focus states | Peony 2pt ring, 2pt offset |
| Reduced motion | Respect `prefers-reduced-motion` — disable all spring/translate animations, keep opacity only |
| Dynamic Type | All type must scale with system font size (iOS) |

> [!IMPORTANT]
> Peony `#C2185B` on White `#FFFFFF` achieves **5.2:1 contrast** — WCAG AA compliant for all text sizes.
> Peony on Ivory `#F5F0E8` achieves **4.7:1** — compliant for body text, marginal for small text. Avoid small Peony text on Ivory backgrounds.

---

## 📍 11. Icon Set

24pt bounding box, 1.8pt stroke, `stroke-linecap: round`, `stroke-linejoin: round`. Lucide Icons library.

| Context | Icon | Colour |
| :--- | :--- | :--- |
| Action mode | `zap` / `flash` | Brass |
| Reflection mode | `leaf` | Sage |
| Urgent | `alert-circle` | Carmine |
| Send | `arrow-up` | White (on Peony button) |
| New chat | `plus` | Peony |
| Delete | `trash-2` | Stone (→ Carmine on hover/press) |
| Calendar | `calendar` | Stone |
| Back | `chevron-left` | Stone |
| Draft email | `pen-line` | Peony |
| Create event | `calendar-plus` | Peony |

---

> [!NOTE]
> **Implementation**: Map all tokens from section 1 to `mobile/src/theme/Theme.ts` and `frontend/src/app/globals.css`. No colour value should ever be hardcoded in a component. If you're typing `#C2185B` in a component file, stop and use the token.
