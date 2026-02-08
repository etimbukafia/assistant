export const Colors = {
    // Base - Boutique Stationery (Light Mode)
    bgBase: '#F9F6F2', // Linen
    bgSurface: '#FFFFFF', // Pure White
    bgElevated: '#FFFFFF', // White cards

    // Accents - Preserved
    accentPrimary: '#7E2E2E', // Rich Auburn
    accentSecondary: '#D97745', // Natural Copper
    accentPrecision: '#1A5F7A', // Teal
    accentMint: '#8A9A5B', // Sage Green (Success)

    // Text - High Contrast for Light Mode
    textPrimary: '#050505', // Obsidian
    textSecondary: '#6B7280', // Muted Gray
    textMuted: '#9CA3AF',   // Light Gray

    // Borders
    border: '#E5E7EB',
    borderLight: '#F3F4F6',
    borderStrong: '#D1D5DB',

    // Status
    success: '#8A9A5B', // Sage Green
    error: '#DC2626', // Red
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
    sm: 6,
    component: 8, // md
    md: 8,
    lg: 12,
    surface: 16, // xl
    xl: 16,
    xxl: 24,
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
    overline: {
        fontFamily: 'Inter_700Bold', // Using Inter Bold for section headers
        fontSize: 11,
        letterSpacing: 1.5,
        textTransform: 'uppercase' as const,
        color: Colors.textMuted,
    },
    logo: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 42,
        letterSpacing: 4,
        textTransform: 'uppercase' as const,
    },
};
