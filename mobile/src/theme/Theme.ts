// =============================================================================
// Teeks Design Tokens — Permanent Ink Palette
// =============================================================================

export const Colors = {
    // -------------------------------------------------------------------------
    // Background
    // -------------------------------------------------------------------------
    bgBase: '#F5F0E8', // Ivory Paper
    bgSurface: '#FFFFFF', // Card / sheet surface
    bgElevated: '#FFFFFF', // Elevated white

    // -------------------------------------------------------------------------
    // Brand Accent — use Peony once per screen, on the primary action only
    // -------------------------------------------------------------------------
    accentPrimary: '#C2185B', // Peony — CTA, send button, active tab
    accentSecondary: '#A07850', // Brass — Action mode icon, secondary interactive
    accentPrecision: '#334155', // Deep Slate — links, informational
    accentMint: '#4D7C0F', // Sage — Reflection mode, success

    // -------------------------------------------------------------------------
    // Text
    // -------------------------------------------------------------------------
    textPrimary: '#18181B', // Ink Black
    textSecondary: '#71717A', // Stone
    textMuted: '#A1A1AA', // Mist — placeholders, disabled

    // -------------------------------------------------------------------------
    // Borders
    // -------------------------------------------------------------------------
    border: '#E4E0D8', // Hairline
    borderLight: '#F0ECE5', // Barely-there
    borderStrong: '#CCC8BF', // Focused inputs, separators

    // -------------------------------------------------------------------------
    // Semantic
    // -------------------------------------------------------------------------
    success: '#4D7C0F', // Sage Green
    error: '#9B1C1C', // Carmine — urgent, destructive, errors
};

export const Spacing = {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
};

export const Radius = {
    xs: 4,   // Pill tags, micro badges
    sm: 6,
    component: 8,   // Buttons, inputs, chips
    md: 8,
    lg: 14,  // Cards, sheets, overlays
    surface: 14,
    xl: 16,
    xxl: 24,
    full: 999, // Avatars, icon containers, mode pills
};

export const Typography = {
    display: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 36,
        lineHeight: 44,
        letterSpacing: -0.7,
    },
    h1: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 28,
        lineHeight: 34,
        letterSpacing: -0.5,
    },
    h2: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 22,
        lineHeight: 28,
        letterSpacing: -0.25,
    },
    bodyLarge: {
        fontFamily: 'Inter_400Regular',
        fontSize: 17,
        lineHeight: 26,
    },
    bodyBase: {
        fontFamily: 'Inter_400Regular',
        fontSize: 15,
        lineHeight: 22,
    },
    label: {
        fontFamily: 'Inter_500Medium',
        fontSize: 13,
        lineHeight: 20,
    },
    caption: {
        fontFamily: 'Inter_400Regular',
        fontSize: 12,
        lineHeight: 18,
    },
    overline: {
        fontFamily: 'Inter_700Bold',
        fontSize: 11,
        lineHeight: 16,
        letterSpacing: 1.2,
        textTransform: 'uppercase' as const,
    },
    logo: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 42,
        letterSpacing: 4,
        textTransform: 'uppercase' as const,
    },
};

// =============================================================================
// Motion — durations in ms. Exits are always faster than entrances.
// =============================================================================
export const Motion = {
    instant: 80,  // Colour state changes (hover, focus)
    fast: 150, // Button feedback, icon transitions
    standard: 250, // Card reveal, opacity fade
    enter: 320, // Sheet / overlay slide-in
    exit: 200, // Sheet / overlay close
};
