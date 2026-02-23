# Teeks: UI Visual Design Guide

This guide describes how the design system translates into specific implementations across screens and platforms. It answers: *what does this look like, precisely?*

---

## 1. Visual Foundation — Permanent Ink on Ivory

The base aesthetic is a premium writing desk: quality paper, dark ink, one deliberate accent colour that tells you where to look.

### Colours in context

| Element | Token | Hex | Rationale |
| :--- | :--- | :--- | :--- |
| App background | `bg-base` | `#F5F0E8` | Ivory Paper — reduces halation in dim environments |
| Cards / surfaces | `bg-surface` | `#FFFFFF` | Clean white lifts above the Ivory — natural paper stack |
| Primary CTA | `accent-peony` | `#C2185B` | The one colour that says *act now* |
| Action mode | `accent-brass` | `#A07850` | Warm, professional, earned |
| Reflection mode | `accent-sage` | `#4D7C0F` | Calm, separate from work mode |
| Body text | `text-primary` | `#18181B` | Near-black, warm — reads as ink, not a screen |
| Borders | `border` | `#E4E0D8` | Hairline — barely there, but the structure holds |

### Typography in context

- **Screen titles** (e.g., "Conversations", "Today"): Playfair Display 22pt, Semi-Bold, Ink Black, left-aligned
- **Card titles**: Inter 15pt, Medium, Ink Black
- **Metadata / timestamps**: Inter 12pt, Regular, Stone `#71717A`
- **Section labels**: Inter 11pt, Bold, Stone, uppercase, +1.2px tracking
- **Input text**: Inter 15pt, Regular, Ink Black
- **Button labels**: Inter 13pt, Semi-Bold — Primary: White on Peony; Secondary: Peony on White

---

## 2. Surface Treatment — Paper Stack Logic

Cards use elevation shadows to create a sense of physical layering — cards sitting on top of the Ivory desk surface.

### Card shadow levels

| Surface | Shadow |
| :--- | :--- |
| Resting card | `0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)` |
| Hovered / pressed | `0 4px 16px rgba(0,0,0,0.09), 0 2px 6px rgba(0,0,0,0.06)` |
| Bottom sheet modal | `0 -8px 30px rgba(0,0,0,0.10), 0 -2px 8px rgba(0,0,0,0.06)` |
| OmniChat overlay | `0 12px 40px rgba(0,0,0,0.14), 0 4px 12px rgba(0,0,0,0.08)` |

Never use `elevation` alone on Android without also specifying a matching web shadow — the values diverge.

---

## 3. Screen-Level Visual Logic

### Today Feed / Chat Sessions List
- Ivory background
- White cards with hairline border
- Urgent cards: 3pt Carmine left border, no other visual treatment
- Section labels in Stone overline style above groups
- Brass loading line at top edge during sync

### Active Chat Session
- Ivory background — the conversation is on warmth, not cold white
- User bubbles: Peony `#C2185B`, white text, `border-bottom-right-radius: 4pt`
- Assistant bubbles: White, Ink Black text, hairline border, `border-bottom-left-radius: 4pt`
- Action cards: Ivory background, Peony header label, Peony primary button

### OmniChat Overlay
- Frosted glass panel — `blur(20px)`, `rgba(255,255,255,0.92)` background
- Hairline white border around the panel edge
- Mode pill: Brass for Action, Sage for Reflection
- Send button: Peony — always Peony

### Calendar
- Clean list view — event title, time, attendee count
- Meeting needing prep: Slate `#334155` left indicator, not Carmine
- Past events: 50% opacity, no action buttons

---

## 4. Platform Specifics

### iOS
- Navigation uses native back gesture (swipe from left) — do not disable
- Safe area insets: Ivory background extends behind the home indicator
- Status bar: `style="dark"` (dark icons on Ivory/White backgrounds)
- Haptics: use `expo-haptics` — see `accessibility_specs.md` for event map
- Tab bar: native-height, Ivory background, Peony active state

### Android
- Bottom navigation bar: Ivory background tinted to match system nav bar
- Haptics: standard Android vibration patterns via `expo-haptics`
- Elevation: use both `elevation` prop and `shadowColor` for cross-platform consistency

### Web
- Focus ring: 2pt Peony `#C2185B`, 2pt offset — see `globals.css`
- Hover states on all interactive elements
- Scrollbars: Peony at 25% opacity (already set in `globals.css`)
- Responsive breakpoints: single-column below 768px; sidebar layout above 1024px

---

## 5. Loading & Empty States

### Loading — Skeleton Screens
- Gradient shimmer: `#E4E0D8 → #F5F0E8 → #E4E0D8`
- Applied as background on card-shaped placeholder elements
- Duration: 1.5s, repeat every 2s
- Never show a full-screen spinner — skeleton implies content is coming

### Empty States — Invitations, Not Apologies

| Screen | Headline | CTA |
| :--- | :--- | :--- |
| No chat sessions | Your conversations appear here. | Start a chat |
| No calendar events | Nothing scheduled today. | — |
| Empty search | No results for that. | — |

**Rule**: Empty state = 1 line of copy + 1 optional CTA. No illustration required. No multi-paragraph explanation. The interface is an invitation to act, not a consolation.

---

> [!IMPORTANT]
> **The Polish Rule**: Before any screen ships, review it at actual device size with actual content. Not placeholder text, not dummy avatars — real email subjects, real names, real timestamps. Designs that look good with "Lorem ipsum" often collapse with real data. Check it.
