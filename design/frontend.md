# Teeks: Frontend Build Instructions

This document guides the implementation of Teeks' web frontend. Every decision here flows from the established design system. Do not deviate from the palette, fonts, or interaction patterns without updating `design_system.md` first.

---

## Aesthetic Direction

**Permanent Ink on Ivory.** A premium writing desk — quality paper, dark ink, one deliberate accent colour that tells you where to look.

This is not a dark mode app. Not glassmorphism. Not a gradient mesh. It is a light, warm, typographically precise interface for professionals who need clarity under pressure.

**The one thing someone remembers about Teeks:** when Peony `#C2185B` appears on screen, they know exactly what to do. Everything else recedes. One colour. One action. One decision.

---

## Fixed Decisions — Do Not Vary

These are settled. Do not reopen them.

### Fonts
| Role | Font | Weight |
| :--- | :--- | :--- |
| Display / H1 / H2 | Playfair Display | 600 SemiBold |
| Everything else | Inter | 400 Regular, 500 Medium, 700 Bold |

Inter is not a default font placeholder. It is precisely the right choice for dense professional UI at 12–15pt. Do not swap it for something "distinctive." Distinctive is Playfair's job.

### Colour Tokens
All values in `globals.css` as `hsl(var(--*))`. Never hardcode hex values in components.

| Token | Value | Role |
| :--- | :--- | :--- |
| `--background` | Ivory `#F5F0E8` | App background |
| `--foreground` | Ink Black `#18181B` | Body text |
| `--primary` | Peony `#C2185B` | One per screen — primary CTA only |
| `--secondary` | Brass `#A07850` | Action mode secondary |
| `--accent` | Deep Slate `#334155` | Links, informational |
| `--destructive` | Carmine `#9B1C1C` | Errors, urgent, delete |
| `--border` | Hairline `#E4E0D8` | Dividers, card outlines |
| `--muted-foreground` | Stone `#71717A` | Metadata, timestamps |

### Radius
- Buttons, inputs, chips: `8pt` (`--radius`)  
- Cards, sheets, panels: `14pt`  
- Avatars, pills: `999pt` (full)

---

## Layout Principles

- **Max content width**: `680px` for reading columns, `1024px` for full layouts
- **Gutter**: `24px` on desktop, `16px` on mobile
- **Vertical rhythm**: base unit `8px` — all spacing is a multiple of 8
- **Left-align everything** — type, headings, labels. Centred body text is for landing pages, not tools
- **One primary action per screen** — if two buttons compete equally, one is in the wrong place

### Responsive
- Below 768px → single column, full-width cards
- 768px–1024px → sidebar collapsed or hidden, content full-width
- 1024px+ → sidebar visible, content area constrained to reading width

---

## Typography Scale

All in `rem`. Base = 16px.

| Role | Size | Weight | Line height |
| :--- | :--- | :--- | :--- |
| Display | 2.25rem (36px) | Playfair 600 | 1.22 |
| H1 | 1.75rem (28px) | Playfair 600 | 1.21 |
| H2 | 1.375rem (22px) | Playfair 600 | 1.27 |
| Body large | 1.0625rem (17px) | Inter 400 | 1.53 |
| Body | 0.9375rem (15px) | Inter 400 | 1.47 |
| Label | 0.8125rem (13px) | Inter 500 | 1.54 |
| Caption | 0.75rem (12px) | Inter 400 | 1.5 |
| Overline | 0.6875rem (11px) | Inter 700 | 1.45 | uppercase, +1.2px tracking |

---

## Motion

All in CSS — no animation library for basic transitions.

```css
/* Standard */ transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1);
/* Fast */     transition: all 150ms ease-out;
/* Instant */  transition: all 80ms ease-out;
/* Exit */     transition: all 200ms cubic-bezier(0.4, 0, 1, 1);
```

Use the Motion library (React) only for:
- OmniChat overlay spring (top-to-bottom)
- Bottom sheet spring entrance
- Shared element card expansion

**prefers-reduced-motion** is already handled globally in `globals.css`. Do not add `prefers-reduced-motion` overrides per-component — the global rule handles it.

---

## Production Checklist

Before any component ships:

- [ ] All colours from `globals.css` tokens — no hardcoded hex
- [ ] Peony appears at most once on the screen
- [ ] Focus ring visible on all interactive elements (Tab key test)
- [ ] Minimum touch target 48×48px on interactive elements
- [ ] Empty state is designed (not a blank div)
- [ ] Error state is designed (not just a red border)
- [ ] Loading state uses skeleton, not a spinner
- [ ] Text readable at 200% browser zoom
- [ ] No `outline: none` without a custom focus replacement
- [ ] `prefers-reduced-motion` covered by global CSS (no per-component override needed)

---

> [!IMPORTANT]
> **The source of truth order**: `design_system.md` > `globals.css` > this file. If there is a conflict, the earlier document wins and this file should be updated to match it, not the other way around.