"use client";

import { DonnaText } from "@/components/ui/DonnaText";
import { ProgressRing } from "./ProgressRing";
import { getTipOfTheDay } from "./tips";
import { Sparkles } from "lucide-react";

interface FocusHeaderProps {
    goalsCompleted: number;
    goalsTotal: number;
}

export function FocusHeader({ goalsCompleted, goalsTotal }: FocusHeaderProps) {
    const today = new Date();
    const dateStr = today.toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
    });
    const tip = getTipOfTheDay();

    return (
        <div className="flex items-start justify-between gap-4">
            <div className="space-y-2 flex-1">
                <DonnaText variant="h2">{dateStr}</DonnaText>
                <div className="flex items-start gap-2 text-copper">
                    <Sparkles size={14} className="mt-0.5 shrink-0" />
                    <DonnaText variant="caption" className="text-copper italic">
                        {tip}
                    </DonnaText>
                </div>
            </div>
            <ProgressRing completed={goalsCompleted} total={goalsTotal} />
        </div>
    );
}
