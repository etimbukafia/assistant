export default {
    async fetch(request, env, ctx) {
        // Handle CORS preflight
        if (request.method === 'OPTIONS') {
            return new Response(null, {
                headers: {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type',
                },
            });
        }

        if (request.method !== 'POST') {
            return new Response('Method not allowed', { status: 405 });
        }

        try {
            const { name, email, linkedin } = await request.json();

            if (!name || !email) {
                return jsonResponse({ error: 'Name and email are required' }, 400);
            }

            // 1. Write to Google Sheet via Apps Script
            if (env.GOOGLE_SCRIPT_URL) {
                await fetch(env.GOOGLE_SCRIPT_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, email, linkedin }),
                });
            }

            // 2. Send email via Resend
            if (env.RESEND_API_KEY && env.NOTIFICATION_EMAIL) {
                await fetch('https://api.resend.com/emails', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
                    },
                    body: JSON.stringify({
                        from: 'Teeks Signup <onboarding@resend.dev>',
                        to: env.NOTIFICATION_EMAIL,
                        subject: `🎉 New Founding Member: ${name}`,
                        html: `
              <h2 style="color: #7E2E2E;">New Founding Member Application</h2>
              <p><strong>Name:</strong> ${name}</p>
              <p><strong>Email:</strong> <a href="mailto:${email}">${email}</a></p>
              <p><strong>LinkedIn:</strong> <a href="${linkedin}">${linkedin}</a></p>
              <hr />
              <p style="color: #888;">Submitted at ${new Date().toISOString()}</p>
            `,
                    }),
                });
            }

            return jsonResponse({ success: true });
        } catch (error) {
            console.error('Worker error:', error);
            return jsonResponse({ error: 'Internal server error' }, 500);
        }
    },
};

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status,
        headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
    });
}
