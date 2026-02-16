"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Loader2 } from "lucide-react";

import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { getTelemetryDashboard } from "@/services/telemetry";

function pct(value: number) {
    return `${Math.round(value * 100)}%`;
}

export default function TelemetryPage() {
    const [days, setDays] = React.useState(7);

    const { data, isLoading, refetch, isFetching } = useQuery({
        queryKey: ["telemetry", "dashboard", days],
        queryFn: () => getTelemetryDashboard(days),
    });

    return (
        <div className="space-y-6">
            <div className="flex items-start justify-between">
                <div>
                    <DonnaText variant="h2" className="text-auburn">Admin Telemetry</DonnaText>
                    <DonnaText variant="body" className="text-muted-foreground">
                        Internal product metrics for chat workflow conversion.
                    </DonnaText>
                </div>
                <div className="flex items-center gap-2">
                    {[7, 14, 30].map((v) => (
                        <DonnaButton
                            key={v}
                            variant={days === v ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => setDays(v)}
                        >
                            {v}d
                        </DonnaButton>
                    ))}
                    <DonnaButton variant="ghost" size="sm" onClick={() => refetch()}>
                        Refresh
                    </DonnaButton>
                </div>
            </div>

            {isLoading ? (
                <div className="h-52 rounded-xl border border-border/60 bg-white/80 flex items-center justify-center">
                    <Loader2 className="h-7 w-7 animate-spin text-auburn" />
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                        <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                            <DonnaText variant="label" className="text-muted-foreground uppercase">Total Events</DonnaText>
                            <DonnaText variant="h3">{data?.total_events || 0}</DonnaText>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                            <DonnaText variant="label" className="text-muted-foreground uppercase">Chip Clicked</DonnaText>
                            <DonnaText variant="h3">{data?.funnel.chip_clicked || 0}</DonnaText>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                            <DonnaText variant="label" className="text-muted-foreground uppercase">Message Sent</DonnaText>
                            <DonnaText variant="h3">{data?.funnel.message_sent || 0}</DonnaText>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                            <DonnaText variant="label" className="text-muted-foreground uppercase">Action Approved</DonnaText>
                            <DonnaText variant="h3">{data?.funnel.action_approved || 0}</DonnaText>
                        </div>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                        <DonnaText variant="h4" className="mb-3 flex items-center gap-2">
                            <BarChart3 size={16} /> Funnel Conversion
                        </DonnaText>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div className="rounded-md bg-linen/40 p-3">
                                <DonnaText variant="label" className="text-muted-foreground uppercase">Click to Send</DonnaText>
                                <DonnaText variant="h3">{pct(data?.funnel.click_to_send_rate || 0)}</DonnaText>
                            </div>
                            <div className="rounded-md bg-linen/40 p-3">
                                <DonnaText variant="label" className="text-muted-foreground uppercase">Send to Approve</DonnaText>
                                <DonnaText variant="h3">{pct(data?.funnel.send_to_approve_rate || 0)}</DonnaText>
                            </div>
                            <div className="rounded-md bg-linen/40 p-3">
                                <DonnaText variant="label" className="text-muted-foreground uppercase">Click to Approve</DonnaText>
                                <DonnaText variant="h3">{pct(data?.funnel.click_to_approve_rate || 0)}</DonnaText>
                            </div>
                        </div>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                        <DonnaText variant="h4" className="mb-3">Daily Trend</DonnaText>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-left text-muted-foreground border-b border-border/50">
                                        <th className="py-2 pr-2">Date</th>
                                        <th className="py-2 pr-2">Chip Clicked</th>
                                        <th className="py-2 pr-2">Message Sent</th>
                                        <th className="py-2 pr-2">Action Approved</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(data?.daily || []).map((row) => (
                                        <tr key={row.date} className="border-b border-border/30">
                                            <td className="py-2 pr-2">{row.date}</td>
                                            <td className="py-2 pr-2">{row.chip_clicked}</td>
                                            <td className="py-2 pr-2">{row.message_sent}</td>
                                            <td className="py-2 pr-2">{row.action_approved}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}

            {isFetching && !isLoading && (
                <DonnaText variant="caption" className="text-muted-foreground">Refreshing telemetry...</DonnaText>
            )}
        </div>
    );
}
