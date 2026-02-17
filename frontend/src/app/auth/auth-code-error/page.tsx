"use client";

import { DonnaText } from "@/components/ui/DonnaText";
import { AlertTriangle, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function AuthCodeErrorPage() {
    return (
        <div className="min-h-screen bg-linen flex flex-col items-center justify-center px-6">
            <div className="max-w-md w-full text-center">
                <div className="mx-auto w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mb-6">
                    <AlertTriangle size={32} className="text-red-500" />
                </div>
                <DonnaText variant="h2" className="font-playfair text-obsidian text-2xl mb-3">
                    Sign-in failed
                </DonnaText>
                <p className="text-faint text-base mb-8 leading-relaxed">
                    We couldn&apos;t complete the Google sign-in. This can happen if the request expired or was cancelled. Please try again.
                </p>
                <Link
                    href="/login"
                    className="inline-flex items-center gap-2 bg-auburn text-white py-3 px-8 rounded-full font-semibold hover:bg-auburn/90 transition-colors"
                >
                    <ArrowLeft size={18} />
                    Back to Login
                </Link>
            </div>
        </div>
    );
}
