"use client";

import * as React from "react";
import { Coins, Loader2, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { DonnaButton } from "@/components/ui/DonnaButton";
import { DonnaText } from "@/components/ui/DonnaText";
import { getAdminTokenUsage } from "@/services/billing";

const DAY_OPTIONS = [7, 14, 30];
const PROVIDER_OPTIONS = [
    { label: "All", value: "" },
    { label: "Gemini", value: "gemini" },
    { label: "Claude", value: "anthropic" },
    { label: "Gemma", value: "huggingface" },
];

function formatNumber(value: number): string {
    return new Intl.NumberFormat("en-US").format(value || 0);
}

function formatUsd(value: number): string {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
        maximumFractionDigits: 4,
    }).format(value || 0);
}

function providerLabel(provider: string): string {
    if (provider === "anthropic") return "Claude";
    if (provider === "gemini") return "Gemini";
    if (provider === "huggingface") return "Gemma / Local";
    return provider || "Unknown";
}

export default function AdminSpendPage() {
    const [days, setDays] = React.useState(30);
    const [provider, setProvider] = React.useState("");

    const { data, isLoading, isFetching, refetch } = useQuery({
        queryKey: ["billing", "admin-token-usage", days, provider],
        queryFn: () => getAdminTokenUsage({ days, provider: provider || undefined, limit: 25 }),
    });

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <DonnaText variant="h2" className="text-auburn">AI Spend</DonnaText>
                    <DonnaText variant="body" className="text-muted-foreground">
                        Audit billable usage by provider, model, and operation across chat and drafting workloads.
                    </DonnaText>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    {DAY_OPTIONS.map((value) => (
                        <DonnaButton
                            key={value}
                            variant={days === value ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => setDays(value)}
                        >
                            {value}d
                        </DonnaButton>
                    ))}
                    <DonnaButton variant="ghost" size="sm" onClick={() => refetch()}>
                        <RefreshCw className="mr-1 h-4 w-4" />
                        Refresh
                    </DonnaButton>
                </div>
            </div>

            <div className="flex flex-wrap gap-2">
                {PROVIDER_OPTIONS.map((option) => (
                    <DonnaButton
                        key={option.label}
                        variant={provider === option.value ? "linen" : "ghost"}
                        size="sm"
                        onClick={() => setProvider(option.value)}
                    >
                        {option.label}
                    </DonnaButton>
                ))}
            </div>

            {isLoading ? (
                <div className="flex h-56 items-center justify-center rounded-xl border border-border/60 bg-white/80">
                    <Loader2 className="h-7 w-7 animate-spin text-auburn" />
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                        <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                            <DonnaText variant="label" className="uppercase text-muted-foreground">Total Spend</DonnaText>
                            <DonnaText variant="h3">{formatUsd(data?.total_cost_usd || 0)}</DonnaText>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                            <DonnaText variant="label" className="uppercase text-muted-foreground">Requests</DonnaText>
                            <DonnaText variant="h3">{formatNumber(data?.total_requests || 0)}</DonnaText>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                            <DonnaText variant="label" className="uppercase text-muted-foreground">Input Tokens</DonnaText>
                            <DonnaText variant="h3">{formatNumber(data?.total_input_tokens || 0)}</DonnaText>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                            <DonnaText variant="label" className="uppercase text-muted-foreground">Output Tokens</DonnaText>
                            <DonnaText variant="h3">{formatNumber(data?.total_output_tokens || 0)}</DonnaText>
                        </div>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                        <DonnaText variant="h4" className="mb-3 flex items-center gap-2">
                            <Coins size={16} />
                            Provider Summary
                        </DonnaText>
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                            {(data?.providers || []).map((row) => (
                                <div key={row.provider} className="rounded-md bg-linen/40 p-4">
                                    <DonnaText variant="label" className="uppercase text-muted-foreground">
                                        {providerLabel(row.provider)}
                                    </DonnaText>
                                    <DonnaText variant="h4" className="mt-1">{formatUsd(row.cost_usd)}</DonnaText>
                                    <DonnaText variant="caption">
                                        {formatNumber(row.request_count)} requests - {formatNumber(row.total_tokens)} tokens
                                    </DonnaText>
                                </div>
                            ))}
                            {(!data?.providers || data.providers.length === 0) && (
                                <div className="rounded-md bg-linen/30 p-4">
                                    <DonnaText variant="body">No usage found for the selected window.</DonnaText>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-white/80 p-4">
                        <DonnaText variant="h4" className="mb-3">Model Breakdown</DonnaText>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border/50 text-left text-muted-foreground">
                                        <th className="py-2 pr-3">Provider</th>
                                        <th className="py-2 pr-3">Model</th>
                                        <th className="py-2 pr-3">Operation</th>
                                        <th className="py-2 pr-3">Requests</th>
                                        <th className="py-2 pr-3">Tokens</th>
                                        <th className="py-2 pr-3">Spend</th>
                                        <th className="py-2">Policy</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(data?.breakdown || []).map((row) => (
                                        <tr key={`${row.provider}:${row.model}:${row.operation}`} className="border-b border-border/30">
                                            <td className="py-2 pr-3">{providerLabel(row.provider)}</td>
                                            <td className="py-2 pr-3 font-mono text-xs">{row.model}</td>
                                            <td className="py-2 pr-3">{row.operation}</td>
                                            <td className="py-2 pr-3">{formatNumber(row.request_count)}</td>
                                            <td className="py-2 pr-3">{formatNumber(row.total_tokens)}</td>
                                            <td className="py-2 pr-3">{formatUsd(row.cost_usd)}</td>
                                            <td className="py-2">
                                                <span
                                                    className={
                                                        row.billable
                                                            ? "rounded-full bg-auburn/10 px-2 py-1 text-xs font-medium text-auburn"
                                                            : "rounded-full bg-emerald-600/10 px-2 py-1 text-xs font-medium text-emerald-700"
                                                    }
                                                >
                                                    {row.billable ? "Billable" : "Free"}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                    {(!data?.breakdown || data.breakdown.length === 0) && (
                                        <tr>
                                            <td colSpan={7} className="py-6 text-center text-muted-foreground">
                                                No model rows found for this filter.
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}

            {isFetching && !isLoading && (
                <DonnaText variant="caption" className="text-muted-foreground">
                    Refreshing spend data...
                </DonnaText>
            )}
        </div>
    );
}
