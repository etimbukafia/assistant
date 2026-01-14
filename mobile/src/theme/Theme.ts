export const Colors = {
    bgBase: '#0B1320', // Midnight Navy
    bgElevated: '#1A2332', // Slightly lighter navy for cards/modals
    accentPrimary: '#800020', // Oxblood / Deep Burgundy
    accentSecondary: '#D97745', // Copper (kept for highlights)
    accentPrecision: '#1E3A8A', // Jewel Navy
    textPrimary: '#FAF9F6', // Cream/Off-white
    textMuted: '#8E95A1', // Cool grey
    border: '#2A3441', // Navy-grey border
    success: '#065F46', // Jewel Emerald
    error: '#EF4444', // Red
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
