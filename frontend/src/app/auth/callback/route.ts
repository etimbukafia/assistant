import { type NextRequest, NextResponse } from 'next/server'
import { createRouteHandlerClient } from '@/utils/supabase/server'

export async function GET(request: NextRequest) {
    const { searchParams, origin } = new URL(request.url)
    const code = searchParams.get('code')
    // if "next" is in param, use it as the redirect URL
    const next = searchParams.get('next') ?? '/dashboard'

    if (code) {
        const forwardedHost = request.headers.get('x-forwarded-host') // original origin before load balancer
        const isLocalEnv = process.env.NODE_ENV === 'development'
        const redirectUrl = isLocalEnv
            ? `${origin}${next}`
            : forwardedHost
                ? `https://${forwardedHost}${next}`
                : `${origin}${next}`

        const response = NextResponse.redirect(redirectUrl)
        const supabase = createRouteHandlerClient(request, response)
        const { error } = await supabase.auth.exchangeCodeForSession(code)
        if (!error) {
            return response
        }
    }

    // return the user to an error page with instructions
    return NextResponse.redirect(`${origin}/auth/auth-code-error`)
}
