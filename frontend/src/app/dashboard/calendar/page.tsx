import { cookies } from "next/headers";
import CalendarClient from "./CalendarClient";

export default async function CalendarPage() {
    const cookieStore = await cookies();
    const initialView = cookieStore.get("teeks_calendar_view")?.value || "month";
    return <CalendarClient initialView={initialView} />;
}
