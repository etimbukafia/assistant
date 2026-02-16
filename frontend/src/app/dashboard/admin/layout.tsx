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
    const supabase = createClient();
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

    return <>{children}</>;
}
