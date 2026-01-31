export const Glass = {
    // Standard Frosted Glass (Cards, Panels)
    default: {
        backgroundColor: 'rgba(255, 255, 255, 0.08)',
        borderColor: 'rgba(255, 255, 255, 0.12)',
        borderWidth: 1,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.1,
        shadowRadius: 12,
    },

    // Heavy Glass (Navigation, Bottom Sheets) - Darker/Blurrier
    heavy: {
        backgroundColor: 'rgba(5, 11, 20, 0.75)',
        borderColor: 'rgba(255, 255, 255, 0.05)',
        borderWidth: 1,
    },

    // Light Glass (Subtle overlays, inactive states)
    light: {
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderColor: 'transparent',
    },

    // Warm Glass (Active states, Copper-tinted)
    warm: {
        backgroundColor: 'rgba(217, 119, 69, 0.12)', // Copper tint
        borderColor: 'rgba(217, 119, 69, 0.3)',
        borderWidth: 1,
    }
};
