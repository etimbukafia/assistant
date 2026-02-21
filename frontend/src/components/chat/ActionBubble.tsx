import { PendingAction, DraftEmailData, CreateEventData, CreateTaskData } from "@/services/chat";
import { PenLine, CalendarPlus, ListTodo } from "lucide-react";
import { cn } from "@/lib/utils";

interface ActionBubbleProps {
    action: PendingAction;
    onApprove: (actionId: string) => void;
    onReject: (actionId: string) => void;
    isApproving?: boolean;
    isRejecting?: boolean;
}

// Button labels per ux_copy.md §5 — "Send", not "Approve". "Dismiss", not "Reject".
function getActionMeta(actionType: string) {
    switch (actionType) {
        case 'draft_email':  return { Icon: PenLine,      label: "Draft Email",  primary: "Send",         secondary: "Edit"        };
        case 'create_event': return { Icon: CalendarPlus,  label: "Create Event", primary: "Confirm",      secondary: "Cancel"      };
        case 'create_task':  return { Icon: ListTodo,      label: "Create Task",  primary: "Add to tasks", secondary: "Dismiss"     };
        default:             return { Icon: PenLine,       label: "Action",       primary: "Approve",      secondary: "Dismiss"     };
    }
}

function renderContent(action: PendingAction) {
    const data = action.action_data as any;

    if (action.action_type === 'draft_email') {
        const email = data as DraftEmailData;
        return (
            <div className="space-y-3">
                {email.to && (
                    <div>
                        <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-0.5 font-inter">To</p>
                        <p className="text-sm font-medium text-foreground font-inter">{email.to.join(', ')}</p>
                    </div>
                )}
                {email.subject && (
                    <div>
                        <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-0.5 font-inter">Subject</p>
                        <p className="text-sm text-foreground font-inter">{email.subject}</p>
                    </div>
                )}
                {email.body && (
                    <div>
                        <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-0.5 font-inter">Message</p>
                        <p className="text-sm text-foreground/80 leading-relaxed italic font-inter">{email.body}</p>
                    </div>
                )}
            </div>
        );
    }

    if (action.action_type === 'create_event') {
        const event = data as CreateEventData;
        return (
            <div className="space-y-1.5">
                {event.title && <p className="text-sm font-medium text-foreground font-inter">{event.title}</p>}
                {event.start_time && (
                    <p className="text-sm text-muted-foreground font-inter">
                        {new Date(event.start_time).toLocaleString([], {
                            weekday: 'long', month: 'short', day: 'numeric',
                            hour: '2-digit', minute: '2-digit'
                        })}
                    </p>
                )}
                {event.attendees && (
                    <p className="text-xs text-muted-foreground font-inter">with {event.attendees.join(', ')}</p>
                )}
            </div>
        );
    }

    if (action.action_type === 'create_task') {
        const task = data as CreateTaskData;
        return (
            <div className="space-y-1.5">
                <p className="text-sm font-medium text-foreground font-inter">{task.title}</p>
                {task.deadline && (
                    <p className="text-xs text-muted-foreground font-inter">
                        Due {new Date(task.deadline).toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })}
                    </p>
                )}
            </div>
        );
    }

    return <p className="text-sm text-muted-foreground font-inter">{JSON.stringify(data)}</p>;
}

export function ActionBubble({ action, onApprove, onReject, isApproving, isRejecting }: ActionBubbleProps) {
    if (action.status !== 'pending') return null;

    const { Icon, label, primary, secondary } = getActionMeta(action.action_type);

    return (
        <div className="flex w-full mb-2 justify-start teeks-bubble-in">
            <div
                className="max-w-[85%] bg-white border border-border rounded-[14px] overflow-hidden"
                style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)' }}
            >
                {/* Header — overline label with icon */}
                <div className="px-4 py-2.5 bg-linen/60 border-b border-border flex items-center gap-2">
                    <div className="h-5 w-5 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <Icon size={11} className="text-primary" />
                    </div>
                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-primary font-inter">{label}</p>
                </div>

                {/* Content */}
                <div className="px-4 py-4">
                    {renderContent(action)}
                </div>

                {/* Actions — Peony primary, neutral secondary */}
                <div className="px-4 py-3 bg-linen/30 border-t border-border flex gap-2">
                    <button
                        className="flex-1 h-9 rounded-[8px] bg-primary text-white text-[13px] font-semibold hover:bg-primary/90 active:scale-[0.97] transition-all disabled:opacity-40 font-inter"
                        onClick={() => onApprove(action.id)}
                        disabled={isApproving || isRejecting}
                    >
                        {isApproving ? "Working…" : primary}
                    </button>
                    <button
                        className="flex-1 h-9 rounded-[8px] border border-border bg-white text-[13px] font-medium text-foreground hover:bg-linen hover:border-muted-foreground/30 active:scale-[0.97] transition-all disabled:opacity-40 font-inter"
                        onClick={() => onReject(action.id)}
                        disabled={isApproving || isRejecting}
                    >
                        {isRejecting ? "Dismissing…" : secondary}
                    </button>
                </div>
            </div>
        </div>
    );
}
