"use server";

import { cookies } from "next/headers";

export async function setCalendarView(view: string) {
    (await cookies()).set("teeks_calendar_view", view, {
        path: "/",
        maxAge: 60 * 60 * 24 * 365,
    });
}
