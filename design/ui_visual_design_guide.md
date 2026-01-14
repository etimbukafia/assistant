# Donna: High-Fidelity UI Visual Design Guide

This guide bridges the gap between wireframes and technical implementation, applying the "Executive Assistant" aesthetic to the product.

---

## 1. Visual Foundation (The Obsidian Standard)

### Color Palette Implementation
| Element | Color | Token | Usage |
| :--- | :--- | :--- | :--- |
| **Surface** | `#050505` | `bg-obsidian` | Main app background, deep & matte. |
| **Primary Identity** | `#7E2E2E` | `accent-auburn` | Donna’s core presence, login state. |
| **Motion Accent** | `#D97745` | `accent-copper` | Highlights, buttons, active states. |
| **Jewel (Success)** | `#065F46` | `jewel-emerald` | Verified insights, positive updates. |
| **Jewel (Urgent)** | `#800020` | `jewel-burgundy`| High-priority interrupts. |
| **Text (Primary)** | `#FAF9F6` | `text-cream` | Main titles and active content. |

### Typography Implementation
- **Headers**: *Playfair Display* (Semi-Bold). Used for "Morning Briefing" titles and Tab headers.
- **Body**: *Inter* (Regular). Used for summaries, tasks, and message thread details.
- **Micro-copy**: *Inter* (Medium, 10pt). Used for contextual tags like `[Priority high]` or `[3h ago]`.

---

## 2. Core Screen Visual Logic

### A. The Dashboard (High-Fi)
- **Glassmorphism**: Use `backdrop-filter: blur(20px)` for the Bottom Navigation and Header.
- **The Pulse**: A subtle `#7E2E2E` (Auburn) glow behind the Donna logo when active.
- **Card Design**: Cards have no borders; they use a deep obsidian (`#0E0E10`) with a Jewel Emerald (Insight) or Jewel Burgundy (Urgent) left accented border.

### B. The Context Switch (Motions)
- **Shared Elements**: When tapping a card, it expands vertically to fill the screen, moving the summary text into the header of the Detail View.
- **State Feedback**: Buttons use haptic feedback (Mobile) and a subtle 2% scale-down on press.

---

## 3. Platform Considerations (iOS & Android)

### iOS Specifics
- **Navigation**: Uses `UINavigationController` style transitions (Slide from right).
- **Icons**: Utilize SF Symbols for system-level actions (Settings, Calendar).
- **Home Indicator**: Obsidian background extends into the home-bar safe area.

### Android Specifics
- **Navigation**: Uses Material-style "Standard Navigation Rail" on tablets or Bottom Nav for mobile.
- **Haptics**: Uses standard Android haptic patterns for "Donna has a result" notifications.

---

## 4. UI States (Visual Polish)

### Loading States
- **Skeleton Screens**: Use a linear gradient shimmer from `#1A1A1B` to `#252526`.
- **The "Copper Orbit"**: An animation showing a Copper dot orbiting the central Auburn core during data sync.

### Empty States
- **Illustration**: Minimalist line art (Jewel Navy lines on Obsidian) of a professional assistant's desk or a sleek leather-bound planner.

---

> [!IMPORTANT]
> **The Polish Rule**: Every touch target must feel "Expensive." Spacing should be generous (16pt to 24pt gutters) to avoid the "cluttered" feeling of traditional email clients.
