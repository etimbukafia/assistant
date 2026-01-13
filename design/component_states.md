# Donna: Component States & Interaction Guide

This document defines the visual and behavioral variations for Donna's UI components to ensure consistency across all user interactions.

---

## 🔘 1. Buttons

| State | Visual Change | Haptics / Feedback |
| :--- | :--- | :--- |
| **Default** | Primary: `accent-red`, Secondary: `border-silver`. | - |
| **Pressed** | Scale down to 98%, brightness reduction 10%. | Light "tock" haptic. |
| **Disabled** | Opacity 40%, Greyscale filter 50%. | - |
| **Loading** | Label hidden, "Cerulean Orbit" spinner centered. | - |
| **Hover (Web)** | Brightness increase 10%, cursor: pointer. | - |

---

## ⌨️ 2. Inputs & Text Areas

| State | Visual Change | Logic |
| :--- | :--- | :--- |
| **Empty** | Placeholder text in `text-muted`. | Initial state. |
| **Focused** | 1px border glow in `accent-cerulean`. | User is typing. |
| **Error** | Border changes to `accent-red`, shake animation. | Validation failed. |
| **Filled** | Text in `text-primary`. | Data entered. |
| **Processing** | Pulsing Cerulean background. | Donna is analyzing input. |

---

## 📇 3. The "Donna Card" States

| Type | Indicator | Behavior |
| :--- | :--- | :--- |
| **Standard** | `bg-elevated`. | Tap to expand. |
| **Urgent** | Left border: 4pt `accent-red`. | Locked at top of feed. |
| **Insight** | Left border: 4pt `accent-cerulean`. | Includes "Cerulean Precision" tag. |
| **Done** | Green check overlay, then 500ms fade-out. | Item resolved. |
| **Snoozed** | Opacity 50%, "Zzz" icon in corner. | Hidden for set duration. |

---

## 🧭 4. Navigation (Tabs & Headers)

### Bottom Tab Bar
- **Active**: Icon & Label change to `text-primary`. Persistent underline pulse.
- **Inactive**: `text-muted`.
- **Badge State**: Small `accent-red` dot on "Feed" or "Tasks" for new items.

### Header Search
- **Idle**: Translucent Obsidian glass.
- **Active**: Expands to full-width, blurs content behind it.

---

## 🌀 5. Global Feedback States

### The "Cerulean Precision" Sync
- **Trigger**: During initial Inbox sync or AI processing.
- **Visual**: A thin Cerulean line progresses across the very top of the screen (0px height to 2px).

### Approval Confirmation
- **Trigger**: User taps `[Approve]` or `[Send]`.
- **Visual**: Brief "Bloom" effect (centered radial gradient expansion) in Cerulean from the point of touch.

---

> [!TIP]
> **Developer Goal**: Use CSS variables or Theme providers to map these states. Avoid hardcoding "red" or "blue" on individual components. Ref: `design_system.md`.
