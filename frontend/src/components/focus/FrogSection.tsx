"use client";

import { useState, useEffect, useRef } from "react";
import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { DonnaCard, DonnaCardContent } from "@/components/ui/DonnaCard";
import type { Task } from "@/services/messages";
import { Zap, ChevronDown, Check, Play } from "lucide-react";

interface FrogSectionProps {
    frogTask: Task | null;
    activeTasks: Task[];
    onSelectFrog: (taskId: number) => void;
    onClearFrog: () => void;
    onComplete: (taskId: number) => void;
    onStart: (taskId: number) => void;
}

const PRIORITY_COLORS: Record<string, string> = {
    urgent: "text-burgundy bg-burgundy/10",
    high: "text-auburn bg-auburn/10",
    normal: "text-teal bg-teal/10",
    low: "text-faint bg-faint/10",
};

export function FrogSection({
    frogTask,
    activeTasks,
    onSelectFrog,
    onClearFrog,
    onComplete,
    onStart,
}: FrogSectionProps) {
    const [showPicker, setShowPicker] = useState(false);
    const pickerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!showPicker) return;
        const handleClickOutside = (e: MouseEvent) => {
            if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
                setShowPicker(false);
            }
        };
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === "Escape") setShowPicker(false);
        };
        document.addEventListener("mousedown", handleClickOutside);
        document.addEventListener("keydown", handleEscape);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
            document.removeEventListener("keydown", handleEscape);
        };
    }, [showPicker]);

    if (!frogTask) {
        return (
            <DonnaCard className="border-2 border-dashed border-auburn/30 bg-auburn/[0.03]">
                <DonnaCardContent className="py-6">
                    <div className="text-center space-y-3">
                        <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-auburn/10">
                            <Zap size={20} className="text-auburn" />
                        </div>
                        <div>
                            <DonnaText variant="body" weight="semibold" className="text-obsidian">
                                Eat the frog!
                            </DonnaText>
                            <DonnaText variant="caption" className="mt-1">
                                Pick your toughest task to tackle first.
                            </DonnaText>
                        </div>
                        <div className="relative inline-block" ref={pickerRef}>
                            <DonnaButton
                                variant="outline"
                                size="sm"
                                onClick={() => setShowPicker(!showPicker)}
                                className="gap-2"
                            >
                                Pick your frog
                                <ChevronDown size={14} />
                            </DonnaButton>
                            {showPicker && activeTasks.length > 0 && (
                                <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 w-72 bg-white rounded-lg border border-border shadow-lg z-10 max-h-48 overflow-y-auto">
                                    {activeTasks.map((task) => (
                                        <button
                                            key={task.id}
                                            onClick={() => {
                                                onSelectFrog(task.id);
                                                setShowPicker(false);
                                            }}
                                            className="w-full text-left px-3 py-2.5 hover:bg-linen transition-colors border-b border-border/40 last:border-b-0"
                                        >
                                            <DonnaText as="span" variant="caption" weight="medium" className="text-obsidian text-sm">
                                                {task.title}
                                            </DonnaText>
                                            {task.priority !== "normal" && task.priority !== "low" && (
                                                <span className={`ml-2 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${PRIORITY_COLORS[task.priority]}`}>
                                                    {task.priority}
                                                </span>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            )}
                            {showPicker && activeTasks.length === 0 && (
                                <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 w-64 bg-white rounded-lg border border-border shadow-lg z-10 p-4 text-center">
                                    <DonnaText variant="caption">No active tasks yet.</DonnaText>
                                </div>
                            )}
                        </div>
                    </div>
                </DonnaCardContent>
            </DonnaCard>
        );
    }

    const isInProgress = frogTask.status === "in_progress";

    return (
        <DonnaCard className="border-2 border-auburn/40 bg-auburn/[0.03]">
            <DonnaCardContent className="py-5">
                <div className="flex items-start gap-3">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-auburn/10 shrink-0 mt-0.5">
                        <Zap size={16} className="text-auburn" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <DonnaText as="span" variant="label" className="text-auburn">
                            EAT THE FROG
                        </DonnaText>
                        <DonnaText variant="body" weight="semibold" className="text-obsidian mt-1">
                            {frogTask.title}
                        </DonnaText>
                        {frogTask.description && (
                            <DonnaText variant="caption" className="mt-1 line-clamp-2">
                                {frogTask.description}
                            </DonnaText>
                        )}
                        <div className="flex items-center gap-2 mt-3">
                            {!isInProgress ? (
                                <DonnaButton
                                    size="sm"
                                    onClick={() => onStart(frogTask.id)}
                                    className="gap-1.5"
                                >
                                    <Play size={12} />
                                    Start
                                </DonnaButton>
                            ) : (
                                <DonnaButton
                                    size="sm"
                                    variant="default"
                                    onClick={() => onComplete(frogTask.id)}
                                    className="gap-1.5 bg-sage hover:bg-sage/90"
                                >
                                    <Check size={12} />
                                    Complete
                                </DonnaButton>
                            )}
                            <DonnaButton
                                size="sm"
                                variant="ghost"
                                onClick={onClearFrog}
                                className="text-faint text-xs"
                            >
                                Change
                            </DonnaButton>
                        </div>
                    </div>
                    {frogTask.priority !== "normal" && frogTask.priority !== "low" && (
                        <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded-full shrink-0 ${PRIORITY_COLORS[frogTask.priority]}`}>
                            {frogTask.priority}
                        </span>
                    )}
                </div>
            </DonnaCardContent>
        </DonnaCard>
    );
}
