import React from 'react';
import {
    View,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    Dimensions,
    Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from '../ui/DonnaText';
import { TeeksWordmark } from '../ui/TeeksWordmark';

const { width } = Dimensions.get('window');

// Card colors matching the design
const CardColors = {
    coral: '#FFF8F8',
    teal: '#F4FBFB',
    lavender: '#F8F7FF',
    cream: '#FFFFFF',
};

interface BriefingCardProps {
    context: string;
    urgent?: boolean;
    items: string[];
    color: keyof typeof CardColors;
    style?: object;
    rotation?: number;
    showPin?: boolean;
}

const BriefingCard: React.FC<BriefingCardProps> = ({
    context,
    urgent,
    items,
    color,
    style,
    rotation = 0,
    showPin = false,
}) => (
    <View
        style={[
            styles.card,
            { backgroundColor: CardColors[color], transform: [{ rotate: `${rotation}deg` }] },
            style,
        ]}
    >
        {showPin && <View style={styles.cardPin} />}
        <View style={styles.cardHeader}>
            <DonnaText style={[styles.cardContext, urgent && styles.cardContextUrgent]}>
                {context}
            </DonnaText>
        </View>
        <View style={styles.actionPoints}>
            {items.map((item, index) => (
                <View key={index} style={styles.actionItem}>
                    <DonnaText style={styles.actionArrow}>→</DonnaText>
                    <DonnaText style={styles.actionText}>{item}</DonnaText>
                </View>
            ))}
        </View>
    </View>
);

interface OnboardingScreenProps {
    onGoogleAuth: () => void;
    onLogin: () => void;
    isLoading?: boolean;
}

export const OnboardingScreen: React.FC<OnboardingScreenProps> = ({
    onGoogleAuth,
    onLogin,
    isLoading = false,
}) => {
    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />
            <ScrollView
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={false}
            >
                {/* Logo */}
                <View style={styles.header}>
                    <TeeksWordmark width={140} height={45} color={Colors.textPrimary} />
                </View>

                {/* Floating Cards */}
                <View style={styles.hero}>
                    <View style={styles.cardsContainer}>
                        {/* Card 4 - Lavender (bottom) */}
                        <BriefingCard
                            context="Your exec's day tomorrow"
                            items={[
                                '6 meetings, 2 conflicts',
                                'Prep sent for the 10am',
                                'Travel docs for Friday ready',
                            ]}
                            color="lavender"
                            rotation={4}
                            style={styles.card4}
                        />

                        {/* Card 3 - Cream */}
                        <BriefingCard
                            context="3 emails need you"
                            items={[
                                'Legal: signature required',
                                'Sarah: reschedule request',
                                'Investor update: FYI only',
                            ]}
                            color="cream"
                            rotation={-3}
                            style={styles.card3}
                        />

                        {/* Card 2 - Teal */}
                        <BriefingCard
                            context="CFO responded on Waystar deal"
                            items={[
                                'They want Thursday call',
                                "I've held 3pm and 4pm",
                                'NDA draft ready for review',
                            ]}
                            color="teal"
                            rotation={2}
                            style={styles.card2}
                        />

                        {/* Card 1 - Coral (top, urgent) */}
                        <BriefingCard
                            context="Board Meeting - Tomorrow 9am"
                            urgent
                            items={[
                                'Q3 numbers need sign-off by tonight',
                                'Tom wants 10 mins before',
                                'Deck v3 ready - 2 open comments',
                            ]}
                            color="coral"
                            rotation={-1.5}
                            style={styles.card1}
                            showPin
                        />
                    </View>
                </View>

                {/* Headline */}
                <View style={styles.content}>
                    <DonnaText style={styles.headline}>
                        Chaos out.{'\n'}
                        <DonnaText style={styles.headlineHighlight}>Clarity</DonnaText> in.
                    </DonnaText>
                    <DonnaText style={styles.subheadline}>
                        Teeks. The Personal Assistant for Executive Assistants
                    </DonnaText>
                </View>

                {/* Auth Buttons */}
                <View style={styles.auth}>
                    <TouchableOpacity
                        style={styles.btnPrimary}
                        onPress={onGoogleAuth}
                        activeOpacity={0.9}
                        disabled={isLoading}
                    >
                        <Ionicons name="logo-google" size={18} color="#FFFFFF" />
                        <DonnaText style={styles.btnPrimaryText}>Continue with Google</DonnaText>
                    </TouchableOpacity>

                    <TouchableOpacity onPress={onLogin} style={styles.loginLink}>
                        <DonnaText style={styles.loginLinkText}>
                            Already have an account? <DonnaText style={styles.loginLinkHighlight}>Log in</DonnaText>
                        </DonnaText>
                    </TouchableOpacity>
                </View>

                {/* Footer */}
                <View style={styles.footer}>
                    <DonnaText style={styles.footerText}>
                        By continuing, you agree to our{' '}
                        <DonnaText
                            style={styles.footerLink}
                            onPress={() => Linking.openURL('https://teeks.ai/terms')}
                        >
                            Terms of Service
                        </DonnaText>
                        {' '}and{' '}
                        <DonnaText
                            style={styles.footerLink}
                            onPress={() => Linking.openURL('https://teeks.ai/privacy')}
                        >
                            Privacy Policy
                        </DonnaText>
                    </DonnaText>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    scrollContent: {
        flexGrow: 1,
        paddingHorizontal: Spacing.lg,
        paddingBottom: Spacing.xl,
    },
    header: {
        alignItems: 'center',
        paddingTop: Spacing.lg,
        marginBottom: Spacing.md,
    },

    // Hero / Cards
    hero: {
        height: 320,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: Spacing.lg,
    },
    cardsContainer: {
        width: 280,
        height: 240,
        position: 'relative',
    },
    card: {
        position: 'absolute',
        width: 240,
        padding: 16,
        borderRadius: 2,
        borderWidth: 1,
        borderColor: 'rgba(0,0,0,0.08)',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 6 },
        shadowOpacity: 0.08,
        shadowRadius: 12,
        elevation: 4,
    },
    card1: {
        zIndex: 4,
        top: -20,
        left: 10,
    },
    card2: {
        zIndex: 3,
        top: 10,
        left: 25,
    },
    card3: {
        zIndex: 2,
        top: 40,
        left: -10,
    },
    card4: {
        zIndex: 1,
        top: 60,
        left: 30,
        opacity: 0.85,
    },
    cardPin: {
        position: 'absolute',
        top: -8,
        left: 16,
        width: 28,
        height: 8,
        backgroundColor: 'rgba(0,0,0,0.1)',
        borderRadius: 1,
    },
    cardHeader: {
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(0,0,0,0.06)',
        paddingBottom: 10,
        marginBottom: 12,
    },
    cardContext: {
        fontSize: 10,
        fontWeight: '700',
        textTransform: 'uppercase',
        letterSpacing: 1,
        color: Colors.textMuted,
    },
    cardContextUrgent: {
        color: Colors.accentPrimary,
    },
    actionPoints: {
        gap: 8,
    },
    actionItem: {
        flexDirection: 'row',
        alignItems: 'flex-start',
    },
    actionArrow: {
        color: Colors.accentSecondary,
        fontWeight: '900',
        marginRight: 8,
        fontSize: 13,
    },
    actionText: {
        flex: 1,
        fontSize: 13,
        fontWeight: '500',
        color: '#1F2937',
        lineHeight: 18,
    },

    // Content
    content: {
        alignItems: 'center',
        marginBottom: Spacing.xl,
    },
    headline: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 40,
        fontWeight: '700',
        lineHeight: 44,
        textAlign: 'center',
        color: Colors.textPrimary,
        letterSpacing: -1,
        marginBottom: Spacing.md,
    },
    headlineHighlight: {
        color: Colors.accentSecondary,
        fontStyle: 'italic',
    },
    subheadline: {
        fontSize: 16,
        color: Colors.textMuted,
        textAlign: 'center',
        lineHeight: 24,
        maxWidth: 320,
    },

    // Auth
    auth: {
        gap: Spacing.md,
        marginBottom: Spacing.lg,
    },
    btnPrimary: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        backgroundColor: Colors.accentPrimary,
        paddingVertical: 16,
        borderRadius: 4,
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 10,
        elevation: 4,
    },
    btnPrimaryText: {
        color: '#FFFFFF',
        fontSize: 15,
        fontWeight: '600',
    },
    loginLink: {
        alignItems: 'center',
        paddingTop: Spacing.sm,
    },
    loginLinkText: {
        fontSize: 14,
        color: Colors.textMuted,
    },
    loginLinkHighlight: {
        color: Colors.accentSecondary,
        fontWeight: '600',
    },

    // Footer
    footer: {
        alignItems: 'center',
        paddingTop: Spacing.md,
    },
    footerText: {
        fontSize: 12,
        color: Colors.textMuted,
        textAlign: 'center',
        lineHeight: 18,
    },
    footerLink: {
        textDecorationLine: 'underline',
    },
});

export default OnboardingScreen;
