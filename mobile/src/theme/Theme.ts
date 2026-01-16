export const Colors = {
    bgBase: '#F9F6F2', // Linen - Higher-quality bond paper feel
    bgElevated: '#FFFFFF', // Pure white for cards to pop against linen
    accentPrimary: '#7E2E2E', // Rich Auburn - Headlines & Primary CTAs
    accentSecondary: '#D97745', // Natural Copper - Icons & Interactive accents
    accentPrecision: '#1E3A8A', // Navy - Structure & Grounding
    textPrimary: '#050505', // Obsidian Black - Maximum legibility
    textMuted: '#6B7280', // Grey for secondary text
    border: '#E5E7EB', // Subtle light border
    borderStrong: '#1E3A8A', // Navy for grounding dividers
    success: '#8A9A5B', // Sage Green - Positive insights
    error: '#800020', // Burgundy - High-priority alerts
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
    xs: 4,
    component: 8,
    surface: 16,
    full: 999,
};

export const Typography = {
    h1: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 36,
        lineHeight: 44,
        letterSpacing: -0.5,
    },
    h2: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 28,
        lineHeight: 34,
        letterSpacing: -0.25,
    },
    bodyLarge: {
        fontFamily: 'Inter_400Regular',
        fontSize: 18,
        lineHeight: 28,
    },
    bodyBase: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        lineHeight: 24,
    },
    labelSmall: {
        fontFamily: 'Inter_400Regular',
        fontSize: 12,
        letterSpacing: 0.6,
        textTransform: 'uppercase' as const,
    },
    caption: {
        fontFamily: 'Inter_400Regular',
        fontSize: 12,
        lineHeight: 18,
    },
    logo: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 42,
        letterSpacing: 4,
        textTransform: 'uppercase' as const,
    },
};
