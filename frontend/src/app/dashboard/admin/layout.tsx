import Link from "next/link";
import { redirect } from "next/navigation";

import { createClient } from "@/utils/supabase/server";

function parseAdminEmails(raw: string | undefined): Set<string> {
    if (!raw) return new Set();
    return new Set(
        raw
            .split(",")
            .map((email) => email.trim().toLowerCase())
            .filter(Boolean)
    );
}

export default async function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const supabase = await createClient();
    const {
        data: { user },
    } = await supabase.auth.getUser();

    if (!user?.email) {
        redirect("/login");
    }

    const admins = parseAdminEmails(process.env.ADMIN_EMAILS);
    if (!admins.has(user.email.toLowerCase())) {
        redirect("/dashboard/chat");
    }

    return (
        <div className="min-h-screen bg-linen/20">
            <div className="mx-auto max-w-6xl px-6 py-8">
                <div className="mb-6 flex flex-wrap items-center gap-3">
                    <Link
                        href="/dashboard/admin/telemetry"
                        className="rounded-full border border-border/70 bg-white px-4 py-2 text-sm font-medium text-obsidian transition-colors hover:bg-linen/70"
                    >
                        Telemetry
                    </Link>
                    <Link
                        href="/dashboard/admin/spend"
                        className="rounded-full border border-border/70 bg-white px-4 py-2 text-sm font-medium text-obsidian transition-colors hover:bg-linen/70"
                    >
                        AI Spend
                    </Link>
                </div>
                {children}
            </div>
        </div>
    );
}
