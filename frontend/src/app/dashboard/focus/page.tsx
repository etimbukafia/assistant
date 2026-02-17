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
    const { data: tasksData } = useTasks({ limit: 200 });
    const { updateDaily } = useFocusMutations();
    const { approve, complete, start, dismiss, update } = useTaskMutations();

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
                onComplete={complete.mutate}
                onStart={start.mutate}
            />

            <DailyGoals goals={goals} onUpdate={handleUpdateGoals} />

            <ActiveTasksList />
        </div>
    );
}
