import React, { useState } from 'react';
import { StyleSheet, View, FlatList, Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Spacing, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import demoData from '../../src/data/demo_state.json';
import FontAwesome from '@expo/vector-icons/FontAwesome';

export default function FocusScreen() {
  const [tasks, setTasks] = useState(demoData.tasks);

  const toggleTask = (id: number) => {
    setTasks(prev => prev.map(task =>
      task.id === id
        ? { ...task, status: task.status === 'done' ? 'pending' : 'done' }
        : task
    ));
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      <FlatList
        data={tasks}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => (
          <Pressable
            onPress={() => toggleTask(item.id)}
            style={[
              styles.taskCard,
              item.status === 'done' && styles.taskDone
            ]}
          >
            <View style={styles.taskInfo}>
              <View style={[
                styles.priorityDot,
                { backgroundColor: item.priority === 'high' ? Colors.accentPrimary : (item.priority === 'medium' ? Colors.accentPrecision : Colors.textMuted) }
              ]} />
              <DonnaText
                variant="bodyLarge"
                style={[
                  styles.taskTitle,
                  item.status === 'done' && styles.textDone
                ]}
              >
                {item.title}
              </DonnaText>
            </View>
            <View style={[
              styles.checkbox,
              item.status === 'done' && styles.checkboxChecked
            ]}>
              {item.status === 'done' && <FontAwesome name="check" size={12} color="#FFFFFF" />}
            </View>
          </Pressable>
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
  listContent: {
    padding: Spacing.md,
  },
  taskCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.bgElevated,
    padding: Spacing.md,
    borderRadius: Radius.surface,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  taskDone: {
    opacity: 0.6,
    borderColor: Colors.success,
  },
  taskInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  priorityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: Spacing.sm,
  },
  taskTitle: {
    fontWeight: '500',
  },
  textDone: {
    textDecorationLine: 'line-through',
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: Colors.textMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxChecked: {
    backgroundColor: Colors.success,
    borderColor: Colors.success,
  },
});
