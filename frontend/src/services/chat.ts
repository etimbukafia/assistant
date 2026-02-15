import { api } from './api';

export interface Message {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    created_at: string;
}

export interface ChatSession {
    id: string;
    snippet: string;
    updated_at: string;
}

export interface SendMessageRequest {
    session_id: string;
    content: string;
    mode: 'action' | 'reflection';
}

export interface CreateSessionRequest {
    initial_message?: string;
    mode?: 'action' | 'reflection';
}

export const chatService = {
    async getSessions(limit = 20, offset = 0): Promise<ChatSession[]> {
        const response = await api.get<ChatSession[]>('/chat/sessions', {
            params: { limit, offset }
        });
        return response.data;
    },

    async createSession(request: CreateSessionRequest): Promise<ChatSession> {
        const response = await api.post<ChatSession>('/chat/sessions', request);
        return response.data;
    },

    async getMessages(sessionId: string): Promise<Message[]> {
        const response = await api.get<Message[]>(`/chat/sessions/${sessionId}/messages`);
        return response.data;
    },

    async sendMessage(request: SendMessageRequest): Promise<Message> {
        const response = await api.post<Message>('/chat/messages', request);
        return response.data;
    },

    async deleteSession(sessionId: string): Promise<void> {
        await api.delete(`/chat/sessions/${sessionId}`);
    }
};
