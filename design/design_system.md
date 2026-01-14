# Donna: Design System & UI Kit

A comprehensive directory of reusable design tokens, components, and structural rules for the Donna application.

---

## 🎨 1. Design Tokens

### Color Palette (The Executive Palette)
| Token | Hex | Usage |
| :--- | :--- | :--- |
| `color-bg-base` | `#050505` | Primary background (Deep Obsidian) |
| `color-bg-elevated` | `#0E0E10`| Card and surface backgrounds |
| `color-accent-primary`| `#7E2E2E` | Action, Identity (Rich Auburn) |
| `color-accent-secondary`| `#D97745` | Highlighs, Motion (Ginger/Copper) |
| `color-accent-precision`| `#1E3A8A` | Professional, Deep context (Jewel Navy) |
| `color-text-primary` | `#FAF9F6` | Headings, Primary Body (Cream) |
| `color-text-muted` | `#8E8E93` | Metadata, Secondary labels |
| `color-success` | `#065F46` | Positive growth (Jewel Emerald) |
| `color-error` (Urgent) | `#800020` | Critical importance (Jewel Burgundy) |
| `color-border` | `#1F1F21` | Subtle dividers and outlines |

### Spacing Scale (Base 4pt)
- **xs**: 4pt
- **sm**: 8pt
- **md**: 16pt (Standard gutter)
- **lg**: 24pt (Section margins)
- **xl**: 32pt (Page padding)

### Radius Rules
- **Component**: 8pt (Buttons, Inputs)
- **Surface**: 16pt (Cards, Sheets)
- **Full**: 999pt (Avatars, Pills)

---

## 🖋️ 2. Typography Scale

| Style | Font | Size / Weight | Letter Spacing |
| :--- | :--- | :--- | :--- |
| **H1** | *Playfair* | 32pt / Semi-Bold | -0.02em |
| **H2** | *Playfair* | 24pt / Semi-Bold | -0.01em |
| **Body (Large)** | *Inter* | 18pt / Regular | 0 |
| **Body (Base)** | *Inter* | 16pt / Regular | 0 |
| **Label (Small)** | *Inter* | 12pt / Medium | 0.05em (Caps) |
| **Caption** | *Inter* | 11pt / Regular | 0 |

---

## 📦 3. Component Library

### Buttons
- **Primary**: Full width, `color-accent-primary`, center text.
- **Secondary**: Outlined (`color-border`), `color-text-primary`.
- **Ghost**: No background/border, `color-text-muted`.
- **Haptic Feedback**: Standard "tock" on iOS, heavy vibration on urgent actions.

### Cards (The "Donna Card")
- **Layout**: 16pt Padding, 16pt Corner Radius.
- **States**: 
  - Standard: Obsidian background.
  - Urgent: 2pt `color-error` (Burgundy) left border.
  - Insight: 2pt `color-success` (Emerald) left border.

### Inputs
- **Text Area**: Flat borderless design, 12pt `color-bg-elevated`, white text.
- **Search**: `color-bg-base` with subtle glassmorphic blur in header.

---

## 📍 4. Icon Set (Lucide Icons)
*Donna uses a consistent 20pt line icon set with a 1.5px stroke.*

- **Dashboard**: `layout-dashboard`
- **Calendar**: `calendar`
- **Tasks**: `check-square`
- **Settings**: `settings`
- **Drafting**: `pen-tool`
- **Sync**: `refresh-cw`
- **Urgent**: `alert-circle` (Jewel Burgundy)
- **Insight**: `zap` (Jewel Emerald)

---

## 📐 5. Layout Grid
- **Columns**: 4 (Mobile)
- **Gutter**: 16pt
- **Margin**: 20pt (Standard edge of screen)

---

> [!IMPORTANT]
> **Implementation Note**: These tokens should be mapped to `theme.js` or `tailwind.config.js` to ensure the "Cerulean Choice" is never applied ad-hoc. 
