"use client";

import { useMemo, useCallback } from "react";
import { FocusHeader } from "@/components/focus/FocusHeader";
import { WeeklyTargetInput } from "@/components/focus/WeeklyTargetInput";
import { FrogSection } from "@/components/focus/FrogSection";
import { DailyGoals } from "@/components/focus/DailyGoals";
import { ActiveTasksList } from "@/components/focus/ActiveTasksList";
import { useDailyFocus, useFocusMutations } from "@/hooks/useFocus";
import { useTasks, useTaskMutations } from "@/hooks/useTasks";
import type { GoalItem } from "@/services/focus";

export default function FocusPage() {
    const { data: dailyFocus, isLoading: focusLoading } = useDailyFocus();
    const { data: tasksData, isLoading: tasksLoading } = useTasks();
    const { updateDaily } = useFocusMutations();
    const { approve, complete, start, dismiss } = useTaskMutations();

    const allTasks = tasksData?.tasks ?? [];

    const activeTasks = useMemo(
        () => allTasks.filter((t) => t.status === "approved" || t.status === "in_progress"),
        [allTasks]
    );

    const handleUpdateGoals = useCallback(
        (goals: GoalItem[]) => {
            updateDaily.mutate({ goals });
        },
        [updateDaily]
    );

    const handleUpdateWeeklyTarget = useCallback(
        (weekly_target: string) => {
            updateDaily.mutate({ weekly_target });
        },
        [updateDaily]
    );

    const handleSelectFrog = useCallback(
        (taskId: number) => {
            updateDaily.mutate({ frog_task_id: taskId });
        },
        [updateDaily]
    );

    const handleClearFrog = useCallback(() => {
        updateDaily.mutate({ frog_task_id: null });
    }, [updateDaily]);

    if (focusLoading) {
        return (
            <div className="max-w-3xl mx-auto py-8 flex justify-center">
                <div className="w-6 h-6 border-2 border-auburn/30 border-t-auburn rounded-full animate-spin" />
            </div>
        );
    }

    const goals = dailyFocus?.goals ?? [];
    const goalsCompleted = dailyFocus?.goals_completed ?? 0;
    const goalsTotal = goals.length > 0 ? goals.length : 3;

    return (
        <div className="max-w-3xl mx-auto space-y-8">
            <FocusHeader goalsCompleted={goalsCompleted} goalsTotal={goalsTotal} />

            <WeeklyTargetInput
                value={dailyFocus?.weekly_target ?? null}
                onSave={handleUpdateWeeklyTarget}
            />

            <FrogSection
                frogTask={dailyFocus?.frog_task ?? null}
                activeTasks={activeTasks}
                onSelectFrog={handleSelectFrog}
                onClearFrog={handleClearFrog}
                onComplete={complete}
                onStart={start}
            />

            <DailyGoals goals={goals} onUpdate={handleUpdateGoals} />

            <ActiveTasksList
                tasks={allTasks}
                isLoading={tasksLoading}
                onApprove={approve}
                onComplete={complete}
                onStart={start}
                onDismiss={dismiss}
            />
        </div>
    );
}
