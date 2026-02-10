import React from 'react';
import { Mail, Sparkles, Shield, Clock } from 'lucide-react';

/**
 * Landing Page
 * 
 * Entry point for unauthenticated users. 
 * Directs to Supabase auth (not directly to Gmail).
 */
const LandingPage = ({ onConnect, demoMode, setDemoMode, onFoundingMember }) => (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col">
        {/* ... existing hero ... */}

        {/* Hero Section */}
        <div className="flex-1 flex items-center justify-center p-6">
            <div className="max-w-lg w-full text-center">
                {/* Logo */}
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 mb-8 shadow-2xl">
                    <Mail className="w-10 h-10 text-white" />
                </div>

                {/* Title */}
                <h1 className="text-4xl font-bold text-white mb-4">
                    Inbox Brain
                </h1>
                <p className="text-xl text-slate-400 mb-8">
                    Your AI-powered email assistant for executive assistants
                </p>

                {/* Features */}
                <div className="grid grid-cols-3 gap-4 mb-10">
                    <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
                        <Sparkles className="w-6 h-6 text-purple-400 mx-auto mb-2" />
                        <p className="text-sm text-slate-300">AI Summaries</p>
                    </div>
                    <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
                        <Clock className="w-6 h-6 text-blue-400 mx-auto mb-2" />
                        <p className="text-sm text-slate-300">Smart Scheduling</p>
                    </div>
                    <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
                        <Shield className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
                        <p className="text-sm text-slate-300">Secure & Private</p>
                    </div>
                </div>

                {/* CTA Card */}
                <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-8 border border-slate-700/50 shadow-xl">
                    <button
                        onClick={onConnect}
                        className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-white hover:bg-gray-50 text-gray-800 font-semibold rounded-xl transition-all duration-200 shadow-lg hover:shadow-xl mb-4"
                    >
                        <svg className="w-5 h-5" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                        </svg>
                        Get Started with Google
                    </button>

                    <p className="text-slate-500 text-sm">
                        Sign in securely with your Google account
                    </p>

                    {/* Demo Mode Toggle */}
                    <div className="mt-6 pt-6 border-t border-slate-700/50">
                        <label className="flex items-center justify-center gap-2 cursor-pointer text-sm text-slate-400 hover:text-slate-300 transition-colors">
                            <input
                                type="checkbox"
                                checked={demoMode}
                                onChange={(e) => setDemoMode(e.target.checked)}
                                className="rounded bg-slate-700 border-slate-600 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-800"
                            />
                            <span>Try Demo Mode (No account needed)</span>
                        </label>
                    </div>
                </div>

                {/* Trust indicators */}
                <p className="mt-8 text-slate-500 text-xs text-center">
                    Your data is encrypted and never shared. Read our{' '}
                    <a href="#" className="text-slate-400 hover:text-white underline">Privacy Policy</a>
                </p>
            </div>
        </div>

        {/* Footer */}
        <footer className="py-8 text-center border-t border-slate-800/50">
            <p className="text-slate-500 text-sm mb-4">© 2026 Inbox Brain. Built for executive assistants.</p>
            <button
                onClick={onFoundingMember}
                className="text-amber-500/80 hover:text-amber-400 text-sm font-medium transition-colors hover:underline"
            >
                Are you an EA? Apply for Founding Member Access ✨
            </button>
        </footer>
    </div>
);

export default LandingPage;
