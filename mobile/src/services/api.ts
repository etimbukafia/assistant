const BASE_URL = 'http://localhost:8000'; // Adjust for your local environment

export const api = {
    async createGhostSession() {
        try {
            const response = await fetch(`${BASE_URL}/auth/ghost`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            if (!response.ok) {
                throw new Error('Failed to create ghost session');
            }
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            // Fallback for demo if backend is not running
            return { user_id: 'demo_user_fallback', status: 'fallback' };
        }
    }
};
