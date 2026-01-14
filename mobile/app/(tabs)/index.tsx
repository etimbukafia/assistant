import React from 'react';
import { StyleSheet, View, FlatList, SafeAreaView } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { DonnaCard } from '../../src/components/ui/DonnaCard';
import { StatusBar } from 'expo-status-bar';
import demoData from '../../src/data/demo_state.json';

export default function DashboardScreen() {
  const router = useRouter();

  const renderHeader = () => (
    <View style={styles.header}>
      <DonnaText variant="h1" style={styles.greeting}>Morning, Donna.</DonnaText>
      <DonnaText variant="bodyLarge" color={Colors.textMuted}>
        3 high-priority items await your decision.
      </DonnaText>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
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
    padding: Spacing.md,
    paddingTop: Spacing.xl,
    marginBottom: Spacing.sm,
  },
  greeting: {
    marginBottom: Spacing.xs,
  },
  listContent: {
    paddingBottom: Spacing.xl,
  },
});
