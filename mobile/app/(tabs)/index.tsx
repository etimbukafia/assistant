import React from 'react';
import { StyleSheet, View, FlatList, SafeAreaView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { DonnaCard } from '../../src/components/ui/DonnaCard';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '../../src/context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import demoData from '../../src/data/demo_state.json';

export default function DashboardScreen() {
  const router = useRouter();
  const { syncStatus } = useAuth();

  const renderBanner = () => {
    if (syncStatus !== 'demo') return null;

    return (
      <View style={styles.banner}>
        <View style={styles.bannerContent}>
          <DonnaText style={styles.bannerTitle}>See how Donna thinks</DonnaText>
          <DonnaText style={styles.bannerSubtitle}>
            These are sample messages. Connect your inbox when you're ready.
          </DonnaText>
          <TouchableOpacity
            style={styles.bannerButton}
            onPress={() => router.push('/auth/activation-explanation' as any)}
          >
            <DonnaText style={styles.bannerButtonText}>Use Donna with my inbox</DonnaText>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const renderHeader = () => (
    <View style={styles.header}>
      <View style={styles.greetingContainer}>
        <DonnaText variant="h1" style={styles.greeting}>Morning, Donna.</DonnaText>
        <DonnaText variant="bodyLarge" color={Colors.textMuted}>
          {syncStatus === 'demo' ? 'Explore your demo workspace' : 'Everything is captured.'}
        </DonnaText>
      </View>
      {renderBanner()}
    </View>
  );

  if (syncStatus === 'processing') {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="dark" />
        <View style={styles.processingContainer}>
          <ActivityIndicator size="large" color={Colors.accentSecondary} />
          <DonnaText style={styles.processingText}>Processing recent messages...</DonnaText>
          <DonnaText style={styles.processingSubtext}>Donna is personalizing your workspace</DonnaText>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      <FlatList
        data={demoData.messages}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={renderHeader}
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => (
          <DonnaCard
            title={item.title}
            sender={item.sender}
            snippet={item.snippet}
            time={item.time}
            insight={item.insight}
            type={item.type as any}
            suggestedAction={item.suggestedAction}
            onPress={() => router.push(`/details/${item.id}`)}
            onActionPress={() => router.push(`/details/${item.id}`)}
          />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bgBase,
  },
  header: {
    paddingTop: Spacing.xl,
    marginBottom: Spacing.sm,
  },
  greetingContainer: {
    paddingHorizontal: Spacing.md,
    marginBottom: Spacing.lg,
  },
  greeting: {
    marginBottom: Spacing.xs,
  },
  banner: {
    backgroundColor: 'rgba(217, 119, 69, 0.1)', // Subtle Copper background
    marginHorizontal: Spacing.md,
    borderRadius: Radius.surface,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: 'rgba(217, 119, 69, 0.2)',
    marginBottom: Spacing.md,
  },
  bannerContent: {
    alignItems: 'flex-start',
  },
  bannerTitle: {
    ...Typography.h2,
    fontSize: 20, // Customize size slightly down from h2
    color: Colors.accentSecondary,
    marginBottom: Spacing.xs,
  },
  bannerSubtitle: {
    ...Typography.bodyBase,
    color: Colors.textMuted,
    marginBottom: Spacing.lg,
    lineHeight: 20,
  },
  bannerButton: {
    backgroundColor: Colors.accentSecondary,
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.md,
    borderRadius: Radius.full,
  },
  bannerButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 14,
  },
  listContent: {
    paddingBottom: Spacing.xl,
  },
  processingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
  },
  processingText: {
    ...Typography.h2,
    color: Colors.textPrimary,
    marginTop: Spacing.xl,
    textAlign: 'center',
  },
  processingSubtext: {
    ...Typography.bodyBase,
    color: Colors.textMuted,
    marginTop: Spacing.sm,
    textAlign: 'center',
  },
});
