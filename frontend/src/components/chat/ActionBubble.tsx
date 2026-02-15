import { PendingAction, DraftEmailData, CreateEventData, CreateTaskData } from "@/services/chat";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { DonnaText } from "@/components/ui/DonnaText";
import { Check, X, FileText, Calendar, ListTodo } from "lucide-react";
import { cn } from "@/lib/utils";

interface ActionBubbleProps {
    action: PendingAction;
    onApprove: (actionId: string) => void;
    onReject: (actionId: string) => void;
    isApproving?: boolean;
    isRejecting?: boolean;
}

export function ActionBubble({ action, onApprove, onReject, isApproving, isRejecting }: ActionBubbleProps) {
    if (action.status !== 'pending') return null;

    // Type Guards
    const isEmail = (data: any): data is DraftEmailData => action.action_type === 'draft_email';
    const isEvent = (data: any): data is CreateEventData => action.action_type === 'create_event';
    const isTask = (data: any): data is CreateTaskData => action.action_type === 'create_task';

    const renderContent = () => {
        const data = action.action_data;

        if (isEmail(data)) {
            return (
                <div className="space-y-2">
                    {data.to && (
                        <div>
                            <DonnaText variant="label" className="text-xs text-muted-foreground uppercase">To</DonnaText>
                            <DonnaText variant="body" className="font-medium text-sm">{data.to.join(', ')}</DonnaText>
                        </div>
                    )}
                    {data.subject && (
                        <div>
                            <DonnaText variant="label" className="text-xs text-muted-foreground uppercase">Subject</DonnaText>
                            <DonnaText variant="body" className="font-medium">{data.subject}</DonnaText>
                        </div>
                    )}
                    {data.body && (
                        <div>
                            <DonnaText variant="label" className="text-xs text-muted-foreground uppercase">Body</DonnaText>
                            <DonnaText variant="body" className="text-sm line-clamp-3 italic text-muted-foreground/80">
                                "{data.body}"
                            </DonnaText>
                        </div>
                    )}
                </div>
            );
        }

        if (isEvent(data)) {
            return (
                <div className="space-y-2">
                    {data.title && <DonnaText variant="body" className="font-medium">{data.title}</DonnaText>}
                    <div className="flex gap-4 text-sm text-muted-foreground">
                        {data.start_time && <span>{new Date(data.start_time).toLocaleString()}</span>}
                    </div>
                    {data.attendees && (
                        <div className="text-xs text-muted-foreground">
                            with {data.attendees.join(', ')}
                        </div>
                    )}
                </div>
            );
        }

        if (isTask(data)) {
            return (
                <div className="space-y-2">
                    <DonnaText variant="body" className="font-medium">{data.title}</DonnaText>
                    {data.deadline && (
                        <div className="text-xs text-muted-foreground">
                            Due: {new Date(data.deadline).toLocaleDateString()}
                        </div>
                    )}
                </div>
            );
        }

        return (
            <DonnaText variant="body" className="text-sm text-muted-foreground">
                {JSON.stringify(data)}
            </DonnaText>
        );
    };

    const getIcon = () => {
        switch (action.action_type) {
            case 'draft_email': return { icon: FileText, label: "Draft Email" };
            case 'create_event': return { icon: Calendar, label: "Schedule Event" };
            case 'create_task': return { icon: ListTodo, label: "Create Task" };
            default: return { icon: FileText, label: "Proposed Action" };
        }
    };

    const { icon: Icon, label } = getIcon();

    return (
        <div className="flex w-full mb-4 justify-start">
            <div className="max-w-[85%] bg-white border border-border/60 rounded-xl shadow-sm overflow-hidden">
                {/* Header */}
                <div className="px-4 py-2 bg-linen/50 border-b border-border/40 flex items-center gap-2">
                    <div className="h-6 w-6 rounded-full bg-auburn/10 flex items-center justify-center">
                        <Icon size={12} className="text-auburn" />
                    </div>
                    <DonnaText variant="label" className="text-auburn font-bold">
                        {label}
                    </DonnaText>
                </div>

                {/* Content Preview */}
                <div className="p-4">
                    {renderContent()}
                </div>

                {/* Actions */}
                <div className="p-2 bg-gray-50/50 flex gap-2">
                    <DonnaButton
                        variant="default"
                        size="sm"
                        className="flex-1 bg-auburn hover:bg-auburn/90 text-white h-9"
                        onClick={() => onApprove(action.id)}
                        disabled={isApproving || isRejecting}
                    >
                        {isApproving ? "Approving..." : (
                            <>
                                <Check size={14} className="mr-2" /> Approve
                            </>
                        )}
                    </DonnaButton>
                    <DonnaButton
                        variant="outline"
                        size="sm"
                        className="flex-1 border-border hover:bg-destructive/10 hover:text-destructive h-9"
                        onClick={() => onReject(action.id)}
                        disabled={isApproving || isRejecting}
                    >
                        {isRejecting ? "Rejecting..." : (
                            <>
                                <X size={14} className="mr-2" /> Reject
                            </>
                        )}
                    </DonnaButton>
                </div>
            </div>
        </div>
    );
}
