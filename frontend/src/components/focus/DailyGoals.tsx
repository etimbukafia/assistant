"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { DonnaText } from "@/components/ui/DonnaText";
import type { GoalItem } from "@/services/focus";
import { Check } from "lucide-react";

interface DailyGoalsProps {
    goals: GoalItem[];
    onUpdate: (goals: GoalItem[]) => void;
}

const PLACEHOLDERS = [
    "What's your #1 priority today?",
    "Second priority...",
    "Third priority...",
];

export function DailyGoals({ goals, onUpdate }: DailyGoalsProps) {
    // Ensure we always have 3 slots
    const [items, setItems] = useState<GoalItem[]>(() => {
        const base = [...goals];
        while (base.length < 3) base.push({ text: "", completed: false });
        return base.slice(0, 3);
    });
    const debounceRef = useRef<ReturnType<typeof setTimeout>>();

    useEffect(() => {
        const base = [...goals];
        while (base.length < 3) base.push({ text: "", completed: false });
        setItems(base.slice(0, 3));
    }, [goals]);

    const save = useCallback(
        (updated: GoalItem[]) => {
            // Only save items with text
            const toSave = updated.filter((g) => g.text.trim());
            if (debounceRef.current) clearTimeout(debounceRef.current);
            debounceRef.current = setTimeout(() => onUpdate(toSave), 500);
        },
        [onUpdate]
    );

    const handleTextChange = (index: number, text: string) => {
        const updated = [...items];
        updated[index] = { ...updated[index], text };
        setItems(updated);
        save(updated);
    };

    const handleToggle = (index: number) => {
        if (!items[index].text.trim()) return;
        const updated = [...items];
        updated[index] = { ...updated[index], completed: !updated[index].completed };
        setItems(updated);
        // Save immediately for check toggles
        const toSave = updated.filter((g) => g.text.trim());
        onUpdate(toSave);
    };

    return (
        <div className="space-y-2">
            <DonnaText variant="label" className="px-1">
                Today&apos;s Goals
            </DonnaText>
            <div className="space-y-2">
                {items.map((item, i) => (
                    <div
                        key={i}
                        className={`flex items-center gap-3 rounded-lg border bg-white/80 px-4 py-3 transition-all duration-200 ${
                            item.completed
                                ? "border-sage/40 bg-sage/[0.04]"
                                : "border-border/60"
                        }`}
                    >
                        <button
                            onClick={() => handleToggle(i)}
                            aria-label={`${item.completed ? "Uncheck" : "Check"} goal ${i + 1}${item.text ? `: ${item.text}` : ""}`}
                            className={`shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all duration-200 focus-visible:ring-2 focus-visible:ring-auburn/40 focus-visible:ring-offset-1 ${
                                item.completed
                                    ? "bg-sage border-sage scale-110"
                                    : item.text.trim()
                                    ? "border-auburn/40 hover:border-auburn"
                                    : "border-border"
                            }`}
                            disabled={!item.text.trim()}
                        >
                            {item.completed && <Check size={10} className="text-white" />}
                        </button>
                        <input
                            type="text"
                            value={item.text}
                            onChange={(e) => handleTextChange(i, e.target.value)}
                            placeholder={PLACEHOLDERS[i]}
                            aria-label={`Goal ${i + 1}`}
                            className={`flex-1 bg-transparent font-inter text-sm outline-none focus-visible:ring-2 focus-visible:ring-auburn/40 rounded transition-all ${
                                item.completed
                                    ? "text-faint line-through"
                                    : "text-obsidian placeholder:text-faint/60"
                            }`}
                        />
                        <span className="text-faint/40 font-inter text-xs font-medium">
                            {i + 1}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
