export const FOCUS_TIPS = [
    "Eat the frog! Tackle your toughest task first thing when your energy is highest.",
    "Set three clear goals. A focused day beats a busy day.",
    "Progress, not perfection. Done is better than perfect.",
    "Single-task. Multitasking is a myth \u2014 depth beats breadth.",
    "Take breaks. A rested mind solves problems faster.",
    "Start small. The hardest part is beginning.",
    "Protect your morning. Guard your peak hours for deep work.",
    "Two-minute rule: if it takes less than two minutes, do it now.",
    "Batch similar tasks. Context-switching drains energy.",
    "End each day by planning tomorrow. You\u2019ll sleep better and start faster.",
];

export function getTipOfTheDay(): string {
    const now = new Date();
    const start = new Date(now.getFullYear(), 0, 0);
    const diff = now.getTime() - start.getTime();
    const dayOfYear = Math.floor(diff / (1000 * 60 * 60 * 24));
    return FOCUS_TIPS[dayOfYear % FOCUS_TIPS.length];
}
