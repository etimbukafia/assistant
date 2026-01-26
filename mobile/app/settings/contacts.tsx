import React, { useState, useEffect } from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Alert, ActivityIndicator, Modal, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { useContacts, useContactMutations } from '@/src/hooks/useContacts';
import { ContactContext } from '@/src/services/memory';

const getCategoryIcon = (category?: string) => {
    switch (category) {
        case 'vip': return { name: 'star', color: '#F1C40F' };
        case 'colleague': return { name: 'briefcase', color: Colors.accentPrecision };
        case 'vendor': return { name: 'cart', color: '#E67E22' };
        case 'external': return { name: 'globe', color: Colors.textSecondary };
        default: return { name: 'person', color: Colors.textMuted };
    }
};

export default function ContactsSettingsScreen() {
    const router = useRouter();
    const [editingContact, setEditingContact] = useState<ContactContext | null>(null);

    const { data: contactsData, isLoading } = useContacts();
    const { updateContact, isUpdating, deleteContact } = useContactMutations();

    const contacts = contactsData?.contacts || [];

    const handleDelete = (contact: ContactContext) => {
        Alert.alert(
            'Delete Contact Context',
            `Are you sure you want to remove all AI context for ${contact.contact_email}?`,
            [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Delete', style: 'destructive', onPress: () => deleteContact(contact.contact_email) }
            ]
        );
    };

    const handleSaveContact = (data: { contact_name?: string; category?: string; preferred_tone?: string }) => {
        if (editingContact) {
            updateContact(
                { email: editingContact.contact_email, data },
                { onSuccess: () => setEditingContact(null) }
            );
        }
    };

    // Header component - reused in loading state
    const Header = () => (
        <View style={styles.header}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
            </TouchableOpacity>
            <DonnaText style={styles.headerTitle}>Contact Intelligence</DonnaText>
            <View style={styles.headerPlaceholder} />
        </View>
    );

    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <Header />
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentSecondary} />
                </View>
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />
            <Header />

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                <DonnaText style={styles.description}>
                    Manage how Donna handles relationships. VIPs get higher priority, and preferred tones influence AI drafts.
                </DonnaText>

                {contacts.length === 0 ? (
                    <View style={styles.emptyState}>
                        <Ionicons name="people-outline" size={48} color={Colors.textMuted} />
                        <DonnaText style={styles.emptyText}>No contacts recognized yet</DonnaText>
                        <DonnaText style={styles.emptySubtext}>
                            Donna automatically learns about people as you interact with them.
                        </DonnaText>
                    </View>
                ) : (
                    <View style={styles.contactsList}>
                        {contacts.map((contact) => {
                            const icon = getCategoryIcon(contact.category);
                            return (
                                <View key={contact.id} style={styles.contactCard}>
                                    <View style={[styles.contactIcon, { backgroundColor: icon.color + '20' }]}>
                                        <Ionicons name={icon.name as any} size={20} color={icon.color} />
                                    </View>
                                    <View style={styles.contactInfo}>
                                        <DonnaText style={styles.contactName}>
                                            {contact.contact_name || contact.contact_email.split('@')[0]}
                                        </DonnaText>
                                        <DonnaText style={styles.contactEmail}>{contact.contact_email}</DonnaText>
                                        <View style={styles.badgeRow}>
                                            <View style={[styles.badge, { backgroundColor: icon.color + '15' }]}>
                                                <DonnaText style={[styles.badgeText, { color: icon.color }]}>
                                                    {(contact.category || 'Standard').toUpperCase()}
                                                </DonnaText>
                                            </View>
                                            {contact.preferred_tone && (
                                                <View style={styles.badge}>
                                                    <DonnaText style={styles.badgeText}>
                                                        {contact.preferred_tone.toUpperCase()} TONE
                                                    </DonnaText>
                                                </View>
                                            )}
                                        </View>
                                    </View>
                                    <View style={styles.contactActions}>
                                        <TouchableOpacity
                                            onPress={() => setEditingContact(contact)}
                                            style={styles.actionIcon}
                                        >
                                            <Ionicons name="pencil-outline" size={20} color={Colors.textSecondary} />
                                        </TouchableOpacity>
                                        <TouchableOpacity
                                            onPress={() => handleDelete(contact)}
                                            style={styles.actionIcon}
                                        >
                                            <Ionicons name="trash-outline" size={20} color={Colors.error} />
                                        </TouchableOpacity>
                                    </View>
                                </View>
                            );
                        })}
                    </View>
                )}
            </ScrollView>

            {/* Edit Modal */}
            <EditContactModal
                visible={!!editingContact}
                contact={editingContact}
                onClose={() => setEditingContact(null)}
                onSave={handleSaveContact}
                isSaving={isUpdating}
            />
        </SafeAreaView>
    );
}

interface EditContactModalProps {
    visible: boolean;
    contact: ContactContext | null;
    onClose: () => void;
    onSave: (data: { contact_name?: string; category?: string; preferred_tone?: string }) => void;
    isSaving: boolean;
}

function EditContactModal({ visible, contact, onClose, onSave, isSaving }: EditContactModalProps) {
    const [name, setName] = useState('');
    const [category, setCategory] = useState<'vip' | 'colleague' | 'external' | 'vendor'>('external');
    const [tone, setTone] = useState<'formal' | 'neutral' | 'casual'>('neutral');

    useEffect(() => {
        if (contact) {
            setName(contact.contact_name || '');
            setCategory(contact.category || 'external');
            setTone(contact.preferred_tone || 'neutral');
        }
    }, [contact]);

    const handleSave = () => {
        onSave({ contact_name: name, category, preferred_tone: tone });
    };

    return (
        <Modal visible={visible} transparent animationType="slide">
            <View style={styles.modalOverlay}>
                <View style={styles.modalContent}>
                    <View style={styles.modalHeader}>
                        <DonnaText style={styles.modalTitle}>Edit Relationship</DonnaText>
                        <TouchableOpacity onPress={onClose}>
                            <Ionicons name="close" size={24} color={Colors.textPrimary} />
                        </TouchableOpacity>
                    </View>

                    <DonnaText style={styles.label}>DISPLAY NAME</DonnaText>
                    <TextInput
                        style={styles.input}
                        value={name}
                        onChangeText={setName}
                        placeholder="Name"
                        placeholderTextColor={Colors.textMuted}
                    />

                    <DonnaText style={styles.label}>CATEGORY</DonnaText>
                    <View style={styles.pickerRow}>
                        {(['vip', 'colleague', 'external', 'vendor'] as const).map((cat) => (
                            <TouchableOpacity
                                key={cat}
                                style={[styles.pickerItem, category === cat && styles.pickerItemActive]}
                                onPress={() => setCategory(cat)}
                            >
                                <DonnaText style={[styles.pickerText, category === cat && styles.pickerTextActive]}>
                                    {cat.toUpperCase()}
                                </DonnaText>
                            </TouchableOpacity>
                        ))}
                    </View>

                    <DonnaText style={styles.label}>TONE PREFERENCE</DonnaText>
                    <View style={styles.pickerRow}>
                        {(['formal', 'neutral', 'casual'] as const).map((t) => (
                            <TouchableOpacity
                                key={t}
                                style={[styles.pickerItem, tone === t && styles.pickerItemActive]}
                                onPress={() => setTone(t)}
                            >
                                <DonnaText style={[styles.pickerText, tone === t && styles.pickerTextActive]}>
                                    {t.toUpperCase()}
                                </DonnaText>
                            </TouchableOpacity>
                        ))}
                    </View>

                    <TouchableOpacity
                        style={[styles.saveBtn, isSaving && styles.saveBtnDisabled]}
                        onPress={handleSave}
                        disabled={isSaving}
                    >
                        {isSaving ? (
                            <ActivityIndicator color="white" />
                        ) : (
                            <DonnaText style={styles.saveBtnText}>Save Changes</DonnaText>
                        )}
                    </TouchableOpacity>
                </View>
            </View>
        </Modal>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    backButton: {
        padding: Spacing.xs,
    },
    headerTitle: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    headerPlaceholder: {
        width: 40,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
    },
    description: {
        fontSize: 14,
        color: Colors.textSecondary,
        marginBottom: Spacing.xl,
        lineHeight: 20,
    },
    contactsList: {
        gap: Spacing.md,
    },
    contactCard: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    contactIcon: {
        width: 40,
        height: 40,
        borderRadius: 20,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: Spacing.md,
    },
    contactInfo: {
        flex: 1,
    },
    contactName: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    contactEmail: {
        fontSize: 12,
        color: Colors.textMuted,
        marginBottom: 6,
    },
    badgeRow: {
        flexDirection: 'row',
        gap: 6,
    },
    badge: {
        paddingHorizontal: 8,
        paddingVertical: 2,
        borderRadius: Radius.full,
        backgroundColor: Colors.border,
    },
    badgeText: {
        fontSize: 10,
        fontWeight: '700',
        color: Colors.textSecondary,
    },
    contactActions: {
        flexDirection: 'row',
        gap: Spacing.xs,
    },
    actionIcon: {
        padding: 8,
    },
    emptyState: {
        alignItems: 'center',
        paddingTop: 60,
    },
    emptyText: {
        fontSize: 16,
        fontWeight: '600',
        color: Colors.textSecondary,
        marginTop: Spacing.md,
    },
    emptySubtext: {
        fontSize: 13,
        color: Colors.textMuted,
        textAlign: 'center',
        marginTop: 4,
        paddingHorizontal: 40,
    },
    // Modal
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0,0,0,0.5)',
        justifyContent: 'flex-end',
    },
    modalContent: {
        backgroundColor: Colors.bgBase,
        borderTopLeftRadius: Radius.xl,
        borderTopRightRadius: Radius.xl,
        padding: Spacing.lg,
        paddingBottom: 40,
    },
    modalHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: Spacing.xl,
    },
    modalTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    label: {
        fontSize: 11,
        fontWeight: '700',
        color: Colors.textMuted,
        letterSpacing: 1,
        marginBottom: 8,
        marginTop: 16,
    },
    input: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.md,
        padding: Spacing.md,
        fontSize: 15,
        color: Colors.textPrimary,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    pickerRow: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 8,
    },
    pickerItem: {
        paddingHorizontal: 12,
        paddingVertical: 8,
        borderRadius: Radius.full,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    pickerItemActive: {
        backgroundColor: Colors.accentSecondary,
        borderColor: Colors.accentSecondary,
    },
    pickerText: {
        fontSize: 12,
        fontWeight: '600',
        color: Colors.textSecondary,
    },
    pickerTextActive: {
        color: 'white',
    },
    saveBtn: {
        backgroundColor: Colors.accentSecondary,
        borderRadius: Radius.full,
        padding: 16,
        alignItems: 'center',
        marginTop: Spacing.xxl,
    },
    saveBtnDisabled: {
        opacity: 0.7,
    },
    saveBtnText: {
        color: 'white',
        fontWeight: '700',
        fontSize: 16,
    },
});
