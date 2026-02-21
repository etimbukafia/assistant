"use client";

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

    return (
        <div>
            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-2 font-inter">
                Focus
            </p>
            <h1 className="font-playfair text-[28px] font-semibold text-foreground leading-tight tracking-tight">
                {dateStr}
            </h1>
        </div>
    );
}
