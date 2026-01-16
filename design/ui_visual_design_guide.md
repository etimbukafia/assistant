# Donna: High-Fidelity UI Visual Design Guide

This guide bridges the gap between wireframes and technical implementation, applying the "Executive Assistant" aesthetic to the product.

---

## 1. Visual Foundation (The Linen Stationery)

### Color Palette Implementation
| Element | Color | Token | Usage |
| :--- | :--- | :--- | :--- |
| **Surface** | `#F9F6F2` | `bg-linen` | Main app background, tactile bond paper. |
| **Primary Identity** | `#7E2E2E` | `accent-auburn` | Headlines and core brand presence. |
| **Motion Accent** | `#D97745` | `accent-copper` | Interactive highlights and active states. |
| **Success/Growth** | `#8A9A5B` | `sage-green` | Tactical approval and positive insights. |
| **Urgent/Priority** | `#800020` | `burgundy` | Critical system interrupts. |
| **Text (Primary)** | `#050505` | `text-obsidian` | High-legibility body copy and summaries. |

### Typography Implementation
- **Headers**: *Playfair Display* (Semi-Bold). Used for "Morning Briefing" titles and Tab headers.
- **Body**: *Inter* (Regular). Used for summaries, tasks, and message thread details.
- **Micro-copy**: *Inter* (Medium, 10pt). Used for contextual tags like `[Priority high]` or `[3h ago]`.

---

## 2. Core Screen Visual Logic

### A. The Dashboard (High-Fi)
- **Paper Stack Logic**: Use elevation shadows to create a sense of cards sitting on top of the Linen foundation.
- **The Auburn Core**: A steady Rich Auburn logo presence in the header.
- **Card Design**: Cards use a Pure White background (`#FFFFFF`) with a Navy (Insight) or Burgundy (Urgent) left accented border for semantic clarity.

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
- **Skeleton Screens**: Use a linear gradient shimmer from `#E5E7EB` to `#F3F4F6` (light grey tones).
- **The "Copper Orbit"**: A Copper rotation animation around an Auburn logo during sync.

### Empty States
- **Illustration**: Minimalist line art (Navy or Auburn lines on Linen) of professional stationery, high-end planners, or an organized executive desk.

---

> [!IMPORTANT]
> **The Polish Rule**: Every touch target must feel "Expensive." Spacing should be generous (16pt to 24pt gutters) to avoid the "cluttered" feeling of traditional email clients.
