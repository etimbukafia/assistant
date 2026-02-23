# Teeks: Accessibility Specifications

> *"Accessibility is not a feature. It is the baseline from which we design."*

Teeks targets **WCAG 2.1 Level AA** across mobile and web. These specs are not a checklist to satisfy at the end — they are constraints that shape every design decision from the start.

---

## 🎨 1. Colour & Contrast

### Contrast Ratios — Permanent Ink Palette

| Pairing | Ratio | Standard | Status |
| :--- | :--- | :--- | :--- |
| Ink Black `#18181B` on Ivory `#F5F0E8` | **14.3:1** | AA / AAA | ✅ Exceeds |
| Ink Black `#18181B` on White `#FFFFFF` | **18.1:1** | AA / AAA | ✅ Exceeds |
| Stone `#71717A` on White `#FFFFFF` | **4.6:1** | AA | ✅ Pass |
| Stone `#71717A` on Ivory `#F5F0E8` | **4.2:1** | AA (large text only) | ⚠️ Use at 14pt+ |
| Peony `#C2185B` on White `#FFFFFF` | **5.2:1** | AA | ✅ Pass |
| Peony `#C2185B` on Ivory `#F5F0E8` | **4.7:1** | AA (body text+) | ✅ Pass at 15pt+ |
| White `#FFFFFF` on Peony `#C2185B` | **5.2:1** | AA | ✅ Pass (buttons) |
| White `#FFFFFF` on Carmine `#9B1C1C` | **8.9:1** | AA / AAA | ✅ Exceeds |
| Mist `#A1A1AA` on White `#FFFFFF` | **2.3:1** | ❌ Insufficient | Placeholders only — never content |

### Colour Dependence Rule
Colour is **never the sole carrier of meaning**. Every colour-coded state has a secondary indicator:

| State | Colour | Secondary indicator |
| :--- | :--- | :--- |
| Urgent | Carmine left border | `alert-circle` icon + "Urgent" label |
| Action mode | Brass | Lightning bolt icon + "ACTION" overline |
| Reflection mode | Sage | Leaf icon + "REFLECTION" overline |
| Error | Carmine text | Error icon + descriptive message |
| Success | Sage | Checkmark icon + confirmation message |
| Active / selected | Peony underline / border | Bold label weight change |

---

## 🖋️ 2. Typography & Dynamic Type

### Minimum sizes
- **Critical content** (message text, card titles, action labels): minimum **15pt**
- **Metadata / timestamps**: minimum **12pt** — never smaller
- **Overlines / status pills**: minimum **11pt**, only ever uppercase with 1.2px tracking for legibility

### Dynamic Type (iOS)
- All type must scale with the system font size setting (`UIContentSizeCategory`)
- **Reflow, never truncate.** Cards expand vertically. Nothing clips at large font sizes.
- Test all screens at `accessibilityExtraExtraExtraLarge` — the largest iOS scaling step
- Fixed-height containers that clip text are a failing condition, not a design decision

### Web text scaling
- Base font size must be defined in `rem`, not `px`, so browser-level text zoom works
- At 200% browser zoom, no content should overlap or disappear

---

## 🔘 3. Touch Targets & Interactivity

### Target sizes
- **Minimum**: 48×48pt on all interactive elements — buttons, icons, selectable cards, tab items
- The 44×44pt recommendation from Apple HIG is a floor; 48pt is our standard
- **Exception**: Inline text links in a paragraph — use `hitSlop` of 10pt on all sides

### Spacing between targets
- Minimum **8pt gap** between adjacent interactive elements
- Minimum **12pt** between destructive actions (Delete, Dismiss) and their neighbours
- The trash icon and the card press target must never overlap

### Focus states (web & keyboard navigation)
- **Focus ring**: 2pt Peony `#C2185B` outline, 2pt offset from element boundary
- Focus ring must be visible on both Ivory and White backgrounds
- Tab order must follow visual reading order — never jump unexpectedly
- No `outline: none` overrides without an equivalent custom focus indicator

---

## 🔈 4. Screen Readers — VoiceOver (iOS) & TalkBack (Android)

### Icon labelling
Every icon without visible text must have an `accessibilityLabel`. Be descriptive, not literal:

| Icon visual | ❌ Bad label | ✅ Good label |
| :--- | :--- | :--- |
| `trash-2` | "Trash" | "Delete conversation" |
| `arrow-up` | "Arrow up" | "Send message" |
| `plus` | "Plus" | "Start new chat" |
| `chevron-left` | "Chevron" | "Go back" |
| `swap-horizontal` | "Swap" | "Switch to Reflection mode" |

### Reading order — Session Card
VoiceOver reads Teeks cards in this exact sequence:
1. Mode (e.g., "Action session")
2. Title (e.g., "Board deck — needs sign-off")
3. Status if urgent (e.g., "Urgent")
4. Timestamp (e.g., "Today at 8:47 AM")
5. Available actions: "Double tap to open. Swipe for delete."

### Reading order — Message thread
1. Role ("Teeks" or "You")
2. Message content
3. Timestamp
4. For action cards: "Draft email — Send or Edit"

### `accessibilityRole` requirements
- Buttons must use `role="button"` — never a `TouchableOpacity` passed off as a decorative element
- Navigation tabs must use `role="tab"` with `aria-selected`
- Session cards are `role="button"` with `aria-label` summarising the session
- Action card Approve/Dismiss buttons use `role="button"` — `aria-describedby` pointing to the action summary

---

## ✨ 5. Motion & Reduced Motion

### `prefers-reduced-motion` (web CSS)
Already implemented in `globals.css`. When active:
- All `transition-duration` and `animation-duration` collapse to `0.01ms`
- Spring physics (OmniChat slide-in) collapses to `opacity` fade only — no `translateY`

### iOS Reduce Motion (`UIAccessibility.isReduceMotionEnabled`)
Check at the hook level. When enabled:
- OmniChat overlay: fade in/out (`opacity` only, 150ms) — no spring translate
- Session card lift on press: disabled — scale stays at 1.0
- Typing indicator: replace pulse animation with a static "•••" text
- All `withSpring` calls replaced with `withTiming(value, { duration: 150 })`

```ts
// Pattern for every animated component
import { AccessibilityInfo } from 'react-native';

const isReduceMotion = await AccessibilityInfo.isReduceMotionEnabled();
const duration = isReduceMotion ? 150 : Motion.enter;
```

---

## 🔊 6. Haptics — Accessibility Utility

Haptics serve as a non-visual confirmation channel. They must be honoured and must be optional.

| Event | Haptic | Accessibility purpose |
| :--- | :--- | :--- |
| Send message | `impactMedium` | Confirms send for users who can't see the UI update |
| Approve action | `impactHeavy` | Consequence confirmation — weight communicates importance |
| Error / failed send | `notificationError` | Distinguishes failure from success without visual check |
| Delete | `notificationWarning` | Warns before irreversible action |

**Haptics must be user-disableable** via `Profile > Accessibility > Haptic feedback`. Default: on.

---

## 🌑 7. Visual Comfort

### Ivory over pure white
Ivory Paper `#F5F0E8` as the base background reduces the halation effect (light bleed from a fully white screen in dark environments). This matters for EAs working early mornings and late evenings.

### Eye strain at scale
- Avoid pure black (`#000000`) text. Ink Black `#18181B` retains contrast while eliminating harshness.
- Line height minimums are non-negotiable. 22pt line height for 15pt body text. Compressed type is hostile to reading.
- Maximum content line length: **680px / ~75 chars**. Beyond this, reading becomes physically tiring.

---

## ✅ 8. Test Protocol

These must be run before every release, not just at QA:

| Test | Tool | Pass condition |
| :--- | :--- | :--- |
| Colour contrast audit | Stark (Figma plugin) or axe | All text pairings ≥ 4.5:1 |
| Dynamic Type stress | iOS Simulator at `XXXL` | No clipped text, no layout overflow |
| VoiceOver full flow | iPhone, VoiceOver on | All interactive elements reachable and labelled |
| Keyboard nav (web) | Tab key through dashboard | Focus ring visible on every element, logical tab order |
| Reduced motion | iOS Accessibility settings | No position-based animation runs |
| Touch target audit | Manual + iOS Accessibility Inspector | All targets ≥ 48×48pt |
| 200% browser zoom | Chrome + Firefox | No content overlap or disappearance |

> [!IMPORTANT]
> **Priority test**: Run the VoiceOver flow through a full Action session — from session list → open session → read messages → approve an action card. This is the most complex accessibility path in the product. If it breaks, nothing else matters.

> [!NOTE]
> Stone `#71717A` on Ivory `#F5F0E8` achieves 4.2:1. This is below the 4.5:1 threshold for small text. Stone on Ivory is only acceptable for text **14pt and above**, or for non-critical metadata. Use Ink Black `#18181B` for anything that must be read.
