# Donna: Component States & Interaction Guide

This document defines the visual and behavioral variations for Donna's UI components to ensure consistency across all user interactions.

---

## 🔘 1. Buttons

| State | Visual Change | Haptics / Feedback |
| :--- | :--- | :--- |
| **Default** | Primary: `accent-auburn`, Secondary: `border-linen`. | - |
| **Pressed** | Scale down to 98%, brightness reduction 5%. | Light "tock" haptic. |
| **Disabled** | Opacity 40%, Greyscale filter 50%. | - |
| **Loading** | Label hidden, "Copper Orbit" spinner centered. | - |
| **Hover (Web)** | Brightness increase 10%, cursor: pointer. | - |

---

## ⌨️ 2. Inputs & Text Areas

| State | Visual Change | Logic |
| :--- | :--- | :--- |
| **Empty** | Placeholder text in `text-muted`. | Initial state. |
| **Focused** | 1px border glow in `accent-auburn` or `navy`. | User is typing. |
| **Error** | Border changes to `burgundy`, shake animation. | Validation failed. |
| **Filled** | Text in `text-primary` (Obsidian). | Data entered. |
| **Processing** | Pulsing Copper background / spinner. | Donna is analyzing input. |

---

## 📇 3. The "Donna Card" States

| Type | Indicator | Behavior |
| :--- | :--- | :--- |
| **Standard** | `bg-white` on `bg-linen`. | Tap to expand. |
| **Urgent** | Left border: 4pt `burgundy`. | Locked at top of feed. |
| **Insight** | Left border: 4pt `navy`. | Includes "Boutique Insight" tag. |
| **Done** | Sage Green check overlay, then 500ms fade-out. | Item resolved. |
| **Snoozed** | Opacity 50%, "Zzz" icon in corner. | Hidden for set duration. |

---

## 🧭 4. Navigation (Tabs & Headers)

### Bottom Tab Bar
- **Active**: Icon & Label change to `accent-auburn` or `copper`.
- **Inactive**: `text-muted`.
- **Badge State**: Small `burgundy` dot on "Inbox" or "Focus" for new items.

### Header Search
- **Idle**: High-visibility white or linen surface.
- **Active**: Expands to full-width, clean shadow elevation.

---

## 🌀 5. Global Feedback States

### The "Boutique Sync"
- **Trigger**: During initial Inbox sync or AI processing.
- **Visual**: A thin Copper line progresses across the very top of the screen.

### Approval Confirmation
- **Trigger**: User taps `[Approve]` or `[Send]`.
- **Visual**: Brief "Bloom" effect (centered radial gradient expansion) in Sage from the point of touch.

---

> [!TIP]
> **Developer Goal**: Use CSS variables or Theme providers to map these states. Avoid hardcoding "red" or "blue" on individual components. Ref: `design_system.md`.
