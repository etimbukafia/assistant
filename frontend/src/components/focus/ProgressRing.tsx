"use client";

interface ProgressRingProps {
    completed: number;
    total: number;
    size?: number;
}

export function ProgressRing({ completed, total, size = 56 }: ProgressRingProps) {
    const strokeWidth = 4;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const progress = total > 0 ? completed / total : 0;
    const offset = circumference - progress * circumference;

    return (
        <div className="relative" style={{ width: size, height: size }} role="progressbar" aria-valuenow={completed} aria-valuemin={0} aria-valuemax={total} aria-label={`${completed} of ${total} goals completed`}>
            <svg width={size} height={size} className="-rotate-90">
                {/* Track */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    className="text-border"
                />
                {/* Progress */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    strokeLinecap="round"
                    className="text-auburn transition-all duration-500 ease-out"
                />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
                <span className="font-inter text-xs font-semibold text-obsidian">
                    {completed}/{total}
                </span>
            </div>
        </div>
    );
}
