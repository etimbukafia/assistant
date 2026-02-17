import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function updateSession(request: NextRequest) {
    let response = NextResponse.next({
        request: {
            headers: request.headers,
        },
    })

    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
            cookies: {
                getAll() {
                    return request.cookies.getAll()
                },
                setAll(cookiesToSet) {
                    cookiesToSet.forEach(({ name, value, options }) => {
                        request.cookies.set({ name, value, ...options })
                        response.cookies.set({ name, value, ...options })
                    })
                },
            },
        }
    )

    const {
        data: { user },
    } = await supabase.auth.getUser()

    // Route Protection Logic
    const path = request.nextUrl.pathname

    // Auth flow pages that require authentication
    const protectedAuthRoutes = ['/auth/subscription', '/auth/setup']
    const isProtectedAuthRoute = protectedAuthRoutes.some(r => path.startsWith(r))

    // Protected Routes
    if (!user && (path.startsWith('/dashboard') || path.startsWith('/chat') || path.startsWith('/settings') || isProtectedAuthRoute)) {
        return NextResponse.redirect(new URL('/login', request.url))
    }

    // Redirect authenticated users away from login (but not from auth flow pages)
    if (user && path === '/login') {
        return NextResponse.redirect(new URL('/dashboard', request.url))
    }

    return response
}
