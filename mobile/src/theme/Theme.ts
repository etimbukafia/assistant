export const Colors = {
    // Base - Luxury Glass (Dark Mode)
    bgBase: '#050B14', // Deep Executive Navy (almost black)
    bgSurface: 'rgba(255, 255, 255, 0.08)', // Glass Surface fallback
    bgElevated: 'rgba(22, 33, 62, 0.6)',

    // Accents - Boutique Stationery preserved in Dark Mode
    accentPrimary: '#7E2E2E', // Rich Auburn - Headlines & Primary CTAs (Glows)
    accentSecondary: '#D97745', // Natural Copper - Icons & Interactive accents (Highlights)
    accentPrecision: '#1A5F7A', // Teal - Precision/Insight (Replaces Navy for contrast)
    accentMint: '#A0E8AF', // Soft Mint - Success/Growth (New)

    // Text
    textPrimary: '#FFFFFF', // White - Maximum legibility on dark
    textSecondary: '#A0AEC0', // Cool Grey
    textMuted: '#64748B',   // Slate

    // Borders
    border: 'rgba(255, 255, 255, 0.1)',
    borderLight: 'rgba(255, 255, 255, 0.05)',
    borderStrong: 'rgba(255, 255, 255, 0.2)',

    // Status
    success: '#8A9A5B', // Sage Green
    error: '#FF6B6B', // Softer Red for dark mode readability
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
