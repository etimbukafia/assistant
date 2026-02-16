"use client";

import { useState, useMemo } from "react";
import { DonnaText } from "@/components/ui/DonnaText";
import { TaskItem } from "./TaskItem";
import type { Task } from "@/services/messages";
import {
    Sparkles,
    AlertCircle,
    Zap,
    Clock,
    CheckCircle,
    ChevronDown,
    ChevronUp,
    Hourglass,
} from "lucide-react";

type TabView = "all" | "pending" | "active" | "waiting";

interface ActiveTasksListProps {
    tasks: Task[];
    isLoading: boolean;
    onApprove: (taskId: number) => void;
    onComplete: (taskId: number) => void;
    onStart: (taskId: number) => void;
    onDismiss: (taskId: number) => void;
}

const TABS: { key: TabView; label: string; activeClass: string }[] = [
    { key: "all", label: "All", activeClass: "bg-obsidian text-white" },
    { key: "pending", label: "Suggested", activeClass: "bg-copper text-white" },
    { key: "active", label: "Active", activeClass: "bg-sage text-white" },
    { key: "waiting", label: "Waiting", activeClass: "bg-[#7B68A8] text-white" },
];

export function ActiveTasksList({
    tasks,
    isLoading,
    onApprove,
    onComplete,
    onStart,
    onDismiss,
}: ActiveTasksListProps) {
    const [activeTab, setActiveTab] = useState<TabView>("all");
    const [showCompleted, setShowCompleted] = useState(false);

    const categories = useMemo(() => {
        const pending = tasks.filter((t) => t.status === "pending_approval");
        const active = tasks.filter((t) => t.status === "approved" || t.status === "in_progress");
        const waiting = tasks.filter((t) => t.status === "waiting_for");
        const completed = tasks.filter((t) => t.status === "completed");
        const urgent = active.filter((t) => t.priority === "urgent");
        return { pending, active, waiting, completed, urgent };
    }, [tasks]);

    const totalActionable = categories.pending.length + categories.active.length + categories.waiting.length;

    const filtered = useMemo(() => {
        switch (activeTab) {
            case "pending": return { pending: categories.pending, active: [], waiting: [] };
            case "active": return { pending: [], active: categories.active, waiting: [] };
            case "waiting": return { pending: [], active: [], waiting: categories.waiting };
            default: return { pending: categories.pending, active: categories.active, waiting: categories.waiting };
        }
    }, [activeTab, categories]);

    const counts: Record<TabView, number> = {
        all: totalActionable,
        pending: categories.pending.length,
        active: categories.active.length,
        waiting: categories.waiting.length,
    };

    return (
        <div className="space-y-4">
            <DonnaText variant="label" className="px-1">Tasks</DonnaText>

            {/* Filter Chips */}
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {TABS.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors whitespace-nowrap ${
                            activeTab === tab.key
                                ? `${tab.activeClass} border-transparent`
                                : "bg-white border-border text-faint hover:text-obsidian"
                        }`}
                    >
                        {tab.label} ({counts[tab.key]})
                    </button>
                ))}
            </div>

            {/* Stats Badges */}
            <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold bg-burgundy/10 text-burgundy border border-burgundy/20">
                    <AlertCircle size={11} />
                    Urgent ({categories.urgent.length})
                </div>
                <div className="flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold bg-copper/10 text-copper border border-copper/20">
                    <Hourglass size={11} />
                    Pending ({categories.pending.length})
                </div>
                <div className="flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold bg-sage/10 text-sage border border-sage/20">
                    <CheckCircle size={11} />
                    Done ({categories.completed.length})
                </div>
            </div>

            {/* Loading */}
            {isLoading && (
                <div className="py-8 text-center">
                    <div className="inline-block w-5 h-5 border-2 border-auburn/30 border-t-auburn rounded-full animate-spin" />
                </div>
            )}

            {/* Sections */}
            {!isLoading && (
                <div className="space-y-5">
                    {/* Pending — Suggested by AI */}
                    {filtered.pending.length > 0 && (
                        <Section icon={<Sparkles size={13} />} title="SUGGESTED BY AI" color="text-copper">
                            {filtered.pending.map((task) => (
                                <TaskItem key={task.id} task={task} onApprove={onApprove} onDismiss={onDismiss} />
                            ))}
                        </Section>
                    )}

                    {/* Urgent — Do Now */}
                    {categories.urgent.length > 0 && (activeTab === "all" || activeTab === "active") && (
                        <Section icon={<AlertCircle size={13} />} title="DO NOW" color="text-burgundy">
                            {categories.urgent.map((task) => (
                                <TaskItem key={task.id} task={task} onComplete={onComplete} onStart={onStart} />
                            ))}
                        </Section>
                    )}

                    {/* Active — Upcoming (non-urgent) */}
                    {filtered.active.filter((t) => t.priority !== "urgent").length > 0 && (
                        <Section icon={<Zap size={13} />} title="UPCOMING" color="text-teal">
                            {filtered.active
                                .filter((t) => t.priority !== "urgent")
                                .map((task) => (
                                    <TaskItem key={task.id} task={task} onComplete={onComplete} onStart={onStart} />
                                ))}
                        </Section>
                    )}

                    {/* Waiting */}
                    {filtered.waiting.length > 0 && (
                        <Section icon={<Clock size={13} />} title="WAITING FOR" color="text-teal">
                            {filtered.waiting.map((task) => (
                                <TaskItem key={task.id} task={task} onStart={onStart} />
                            ))}
                        </Section>
                    )}

                    {/* Empty State */}
                    {filtered.pending.length === 0 && filtered.active.length === 0 && filtered.waiting.length === 0 && (
                        <div className="py-8 text-center">
                            <DonnaText variant="caption">
                                Nothing here yet. Tasks from your emails will appear here.
                            </DonnaText>
                        </div>
                    )}

                    {/* Completed (collapsible) */}
                    {categories.completed.length > 0 && (
                        <div>
                            <button
                                onClick={() => setShowCompleted(!showCompleted)}
                                className="flex items-center justify-between w-full py-3 px-1 border-t border-border/60"
                            >
                                <DonnaText as="span" variant="caption" weight="semibold" className="text-faint">
                                    Completed ({categories.completed.length})
                                </DonnaText>
                                {showCompleted ? <ChevronUp size={16} className="text-faint" /> : <ChevronDown size={16} className="text-faint" />}
                            </button>
                            {showCompleted && (
                                <div className="space-y-1.5">
                                    {categories.completed.map((task) => (
                                        <TaskItem key={task.id} task={task} />
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function Section({
    icon,
    title,
    color,
    children,
}: {
    icon: React.ReactNode;
    title: string;
    color: string;
    children: React.ReactNode;
}) {
    return (
        <div className="space-y-1.5">
            <div className={`flex items-center gap-1.5 ${color}`}>
                {icon}
                <span className="text-[11px] font-bold tracking-widest uppercase">{title}</span>
            </div>
            {children}
        </div>
    );
}
