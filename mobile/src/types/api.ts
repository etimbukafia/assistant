export interface Task {
    id: number;
    message_id: number;
    title: string;
    description?: string;
    priority: 'low' | 'normal' | 'high' | 'urgent';
    status: 'pending_approval' | 'approved' | 'in_progress' | 'completed' | 'dismissed' | 'waiting_for';
    deadline?: string;
    deadline_source?: 'explicit' | 'inferred';
    deadline_user_confirmed?: boolean;
    urgency_suggested_by_ai?: boolean;
    source_snippet?: string;
}

export interface Message {
    id: number;
    message_id: string; // Gmail ID
    thread_id: string;
    subject: string;
    sender: string;
    recipient: string;
    body: string;
    received_at: string;
    summary?: string;
    needs_reply: boolean;
    extracted_tasks?: string[];
    extracted_dates?: string[];
    extracted_people?: string[];
    processed: boolean;
    start_date?: string; // For calendar/meeting intents
    scheduling_intent?: boolean;
    tasks?: Task[];
}

export interface MessagesListResponse {
    messages: Message[];
    total: number;
}
