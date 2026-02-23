"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Target, Check } from "lucide-react";

interface WeeklyTargetInputProps {
    value: string | null;
    onSave: (value: string) => void;
}

export function WeeklyTargetInput({ value, onSave }: WeeklyTargetInputProps) {
    const [text, setText] = useState(value ?? "");
    const [saved, setSaved] = useState(false);
    const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

    useEffect(() => {
        setText(value ?? "");
    }, [value]);

    const handleChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const newVal = e.target.value;
            setText(newVal);
            setSaved(false);

            if (debounceRef.current) clearTimeout(debounceRef.current);
            debounceRef.current = setTimeout(() => {
                onSave(newVal);
                setSaved(true);
                setTimeout(() => setSaved(false), 1500);
            }, 500);
        },
        [onSave]
    );

    return (
        <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-white/50 px-4 py-3">
            <Target size={16} className="text-primary shrink-0" />
            <input
                type="text"
                value={text}
                onChange={handleChange}
                placeholder="What's your target this week?"
                aria-label="Weekly target"
                className="flex-1 bg-transparent font-inter text-sm text-foreground placeholder:text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary/30 rounded"
            />
            {saved && (
                <div className="flex items-center gap-1 text-sage animate-in fade-in duration-200">
                    <Check size={12} />
                    <span className="font-inter text-xs text-sage">Saved</span>
                </div>
            )}
        </div>
    );
}
