"use client";

import React from "react";

interface State {
    hasError: boolean;
}

export class DashboardErrorBoundary extends React.Component<
    { children: React.ReactNode },
    State
> {
    constructor(props: { children: React.ReactNode }) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError(): State {
        return { hasError: true };
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 px-6">
                    <p className="text-[15px] text-foreground font-medium">Something went wrong.</p>
                    <button
                        onClick={() => this.setState({ hasError: false })}
                        className="text-[13px] text-primary hover:underline"
                    >
                        Try again
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
