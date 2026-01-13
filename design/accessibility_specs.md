# Donna: Accessibility Specs

Donna is designed to be accessible to all executive assistants, regardless of how they interact with their devices. Our goal is WCAG 2.1 Level AA compliance.

---

## 🎨 1. Contrast & Color

### Contrast Ratios
- **Primary Text**: Maintain a minimum 7:1 ratio against the Obsidian background (`#0A0A0B`).
- **Secondary/Muted Text**: Maintain a minimum 4.5:1 ratio.
- **Interactive Elements**: All essential icons and borders must maintain a 3:1 ratio.

### Color Dependence
- **Red/Cerulean Meaning**: Donna never uses color alone to convey meaning.
  - Urgent items include an `alert-circle` icon and text label.
  - Insights include a `zap` icon and "Precision" tag.

---

## 🖋️ 2. Typography & Scaling

### Dynamic Type Support
- Donna supports system-wide font scaling.
- **Scaling Behavior**: Layouts must reflow vertically. Cards should expand in height rather than truncating text at larger font sizes.
- **Minimum Font Size**: No critical information should be presented in less than 12pt.

---

## 🔘 3. Touch Targets & Interactivity

### Target Sizes
- **Minimum Size**: All interactive elements (buttons, links, selectable cards) must be at least **44x44 pt**.
- **Edge Padding**: Maintain a 10pt "Safe Zone" between adjacent interactive elements to prevent accidental taps.

### Focus States
- For keyboard or assistive device navigation, focus is indicated by a 2pt `accent-cerulean` border and a subtle background lift.

---

## 🔈 4. Assistive Technology

### Screen Readers (VoiceOver/TalkBack)
- **Alt-Text**: All icons have descriptive text (e.g., "Sync messages" instead of "refresh-cw").
- **Card Reading Order**: Donna Cards are read in the following sequence:
  1. Priority/Status (Urgent/FYI).
  2. Sender.
  3. AI Summary.
  4. Actions available.

### Haptics & Sound
- Critical actions (Handled, Sent) provide haptic confirmation for users with visual impairments.
- Haptics can be toggled in `Profile > Accessibility`.

---

## 🌑 5. Visual Comfort

- **Reduced Motion**: If "Reduced Motion" is enabled on the device, all slide and expand transitions revert to immediate cross-fades (100ms).
- **Dark Mode Optimization**: Since Donna is Obsidian-first, we ensure that OLED smearing is minimized by using `#0A0A0B` (slightly above pure black) for the base background.

---

> [!IMPORTANT]
> **Implementation Checklist**: Always test screen reader flow on the "Morning Briefing" carousel—it is the most complex navigational component in the app.
