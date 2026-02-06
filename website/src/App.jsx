import React, { useState, useEffect } from 'react';

const App = () => {
  const [formState, setFormState] = useState({
    name: '',
    email: '',
    linkedin: '',
    submitted: false,
    submitting: false,
    error: null
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormState(prev => ({ ...prev, submitting: true, error: null }));

    const { name, email, linkedin } = formState;

    try {
      // Submit to Cloudflare Worker (handles both Google Sheet + Email)
      const workerUrl = import.meta.env.VITE_NOTIFY_WORKER_URL;

      if (workerUrl) {
        await fetch(workerUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, linkedin })
        });
      }

      setFormState(prev => ({ ...prev, submitted: true, submitting: false }));
    } catch (error) {
      console.error('Submission error:', error);
      setFormState(prev => ({ ...prev, submitted: true, submitting: false }));
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">

      {/* Fixed Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-[#0a0a0a]/80 border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center">
            <img src="/teeks-wordmark.svg" alt="Teeks Logo" className="h-8" />
          </div>
          <div className="flex items-center gap-6">
            <button
              onClick={() => document.getElementById('apply').scrollIntoView({ behavior: 'smooth' })}
              className="text-sm px-4 py-2 rounded-lg bg-[#7E2E2E] text-[#F9F6F2] font-medium hover:bg-[#8B3A3A] transition-colors"
            >
              Get Access
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <header className="relative min-h-screen flex items-center pt-16">
        {/* Subtle gradient orb */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-[#7E2E2E]/[0.05] rounded-full blur-[120px] pointer-events-none" />

        <div className="relative max-w-7xl mx-auto px-6 lg:px-8 py-24">
          <div className="max-w-3xl">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#7E2E2E]/10 border border-[#7E2E2E]/20 mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D97745] animate-pulse" />
              <span className="text-xs font-medium text-[#D97745] uppercase tracking-wider">Founding access limited to 50 Executive Assistants</span>
            </div>

            <h1 className="font-serif text-5xl sm:text-6xl lg:text-7xl text-white leading-[1.1] mb-4">
              Built for the ones who<br />
              <span className="text-[#D97745]">make it all happen.</span>
            </h1>

            <h2 className="text-xl sm:text-2xl text-white/90 font-medium mb-6">
              The personal assistant built exclusively for Executive Assistants.
            </h2>

            <p className="text-lg text-white/60 leading-relaxed max-w-xl mb-6">
              Many AI tools are built around Executives. Teeks was built for Executive Assistants. It holds context, tracks decisions, and surfaces what matters without adding noise to your day.
            </p>

            <p className="text-lg text-white/60 leading-relaxed max-w-xl mb-10">
              An EA’s day is a mosaic of a thousand moving pieces. Teeks helps you manage them quietly, so the bigger picture becomes a masterpiece. Secure, thoughtful, and designed to assist you.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 mb-4">
              <button
                onClick={() => document.getElementById('apply').scrollIntoView({ behavior: 'smooth' })}
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-lg bg-[#7E2E2E] text-[#F9F6F2] font-medium hover:bg-[#8B3A3A] transition-all hover:shadow-lg hover:shadow-[#7E2E2E]/20"
              >
                Request Founding Access
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
              </button>
              <button
                onClick={() => document.getElementById('features').scrollIntoView({ behavior: 'smooth' })}
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-lg border border-white/10 text-white/80 font-medium hover:bg-white/5 hover:border-white/20 transition-all"
              >
                See what's different
              </button>
            </div>
            <p className="text-sm text-white/40 italic">
              Founding members get early access to new features and locked-in pricing as Teeks grows.
            </p>
          </div>
        </div>
      </header>

      {/* The Promise */}
      <section className="py-24 bg-[#111111]">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="max-w-4xl mx-auto text-center mb-16">
            <p className="text-[#D97745] text-sm uppercase tracking-widest mb-4">Founding Member Promise</p>
            <h2 className="font-serif text-3xl sm:text-4xl text-white mb-6">
              An invitation.
            </h2>
            <p className="text-white/50 text-lg">
              We’re opening this to 50 Executive Assistants who want a real hand in shaping what Teeks becomes.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            {/* Card 1: Influence */}
            <div className="group relative p-8 rounded-2xl bg-gradient-to-br from-[#161616] to-[#0a0a0a] border border-white/[0.08] hover:border-[#D97745]/40 transition-all duration-300 hover:shadow-2xl hover:shadow-[#D97745]/10">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[#D97745]/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="h-10 w-10 rounded-full bg-[#D97745]/10 flex items-center justify-center mb-6 group-hover:bg-[#D97745]/20 transition-colors">
                <svg className="w-5 h-5 text-[#D97745]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 11.5V14m0-2.5v-6a1.5 1.5 0 113 0m-3 6a1.5 1.5 0 00-3 0v2a7.5 7.5 0 0015 0v-5a1.5 1.5 0 00-3 0m-6-3V11m0-5.5v-1a1.5 1.5 0 013 0v1m0 0V11m0-5.5a1.5 1.5 0 013 0v3m0 0V11" />
                </svg>
              </div>
              <h3 className="font-serif text-xl text-white mb-3 group-hover:text-[#D97745] transition-colors duration-300">Influence</h3>
              <p className="text-white/50 text-sm leading-relaxed">
                Your needs turn into features. Your feedback directly shapes the roadmap.
              </p>
            </div>

            {/* Card 2: Founding Access */}
            <div className="group relative p-8 rounded-2xl bg-gradient-to-br from-[#161616] to-[#0a0a0a] border border-white/[0.08] hover:border-[#D97745]/40 transition-all duration-300 hover:shadow-2xl hover:shadow-[#D97745]/10">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[#D97745]/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="h-10 w-10 rounded-full bg-[#D97745]/10 flex items-center justify-center mb-6 group-hover:bg-[#D97745]/20 transition-colors">
                <svg className="w-5 h-5 text-[#D97745]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
                </svg>
              </div>
              <h3 className="font-serif text-xl text-white mb-3 group-hover:text-[#D97745] transition-colors duration-300">Founding Access</h3>
              <p className="text-white/50 text-sm leading-relaxed">
                You’ll be first to use new capabilities as they’re built. That includes experimental features and improvements long before they’re released publicly.
              </p>
            </div>

            {/* Card 3: Locked-in Pricing */}
            <div className="group relative p-8 rounded-2xl bg-gradient-to-br from-[#161616] to-[#0a0a0a] border border-white/[0.08] hover:border-[#D97745]/40 transition-all duration-300 hover:shadow-2xl hover:shadow-[#D97745]/10">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[#D97745]/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="h-10 w-10 rounded-full bg-[#D97745]/10 flex items-center justify-center mb-6 group-hover:bg-[#D97745]/20 transition-colors">
                <svg className="w-5 h-5 text-[#D97745]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 6h.008v.008H6V6z" />
                </svg>
              </div>
              <h3 className="font-serif text-xl text-white mb-3 group-hover:text-[#D97745] transition-colors duration-300">Locked-In Pricing</h3>
              <p className="text-white/50 text-sm leading-relaxed">
                Your founding rate is secured for life. As Teeks grows and pricing evolves for future users, your rate never changes.
              </p>
            </div>
          </div>
        </div>
      </section>


      {/* Features - Auto Carousel */}
      <section id="features" className="py-24 bg-[#111111] overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="font-serif text-3xl sm:text-4xl text-white">
              How's Teeks different?
            </h2>
            <br />
            <p className="text-[#D97745] font-medium mb-12 text-center">Built for assistants who carry the context, the pressure, and the responsibility</p>

          </div>

          <FeatureCarousel />
        </div>
      </section>

      {/* Chat Modes Section */}
      <section className="py-24 bg-[#111111] overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="text-center mb-16">
            <span className="text-[#D97745] text-sm uppercase tracking-widest block mb-4">Interaction Models</span>
            <h2 className="font-serif text-3xl sm:text-4xl text-white">
              Two modes. One assistant.
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-4 max-w-3xl mx-auto">
            <div className="p-8 rounded-2xl bg-[#161616] border border-white/[0.06] text-left hover:border-[#D97745]/30 transition-all duration-300 group hover:bg-[#1a1a1a]">
              <div className="h-12 w-12 rounded-full bg-white/5 flex items-center justify-center mb-6 group-hover:bg-[#D97745]/10 transition-colors">
                <svg className="w-6 h-6 text-white/70 group-hover:text-[#D97745] transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="font-serif text-2xl text-white mb-3">Action Mode</h3>
              <p className="text-white/50 text-base leading-relaxed">
                Do. Draft emails, schedule meetings, and manage tasks. Teeks handles the execution so you can focus on leading.
              </p>
            </div>

            <div className="p-8 rounded-2xl bg-[#161616] border border-white/[0.06] text-left hover:border-[#D97745]/30 transition-all duration-300 group hover:bg-[#1a1a1a]">
              <div className="h-12 w-12 rounded-full bg-white/5 flex items-center justify-center mb-6 group-hover:bg-[#D97745]/10 transition-colors">
                <svg className="w-6 h-6 text-white/70 group-hover:text-[#D97745] transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
                </svg>
              </div>
              <h3 className="font-serif text-2xl text-white mb-3">Reflection Mode</h3>
              <p className="text-white/50 text-base leading-relaxed">
                Burnout is the enemy. A private, judgment-free space to think out loud, process frustration, and regain perspective before stepping back into the chaos. Teeks listens.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Trust Section */}
      <section className="py-24 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="max-w-3xl mx-auto">
            <p className="text-[#D97745] text-sm uppercase tracking-widest mb-4 text-center">The fear you're not saying out loud</p>
            <h2 className="font-serif text-3xl sm:text-4xl text-white mb-8 text-center">
              "What if my executive's emails leak?"
            </h2>
            <div className="space-y-6 text-white/60 leading-relaxed">
              <p>
                We hear you. That fear is the reason many Executive Assistants have stayed away from AI tools for important and sensitive work.
                Honestly? That fear is justified.
                You are trusted with sensitive conversations, private decisions, and information that cannot afford mistakes. Your reputation depends on discretion.
              </p>
              <p>
                Here's what we do differently:
              </p>
              <ul className="space-y-3 text-white/70">
                <li className="flex gap-3">
                  <span className="text-[#D97745] mt-1">→</span>
                  <span><strong className="text-white"> Your email content is encrypted.</strong> We use industry standard encryption so your data stays protected.</span>
                </li>
                <li className="flex gap-3">
                  <span className="text-[#D97745] mt-1">→</span>
                  <span><strong className="text-white">You stay in control of your data.</strong> If you delete your account, your data is permanently removed within 24 hours. No hidden backups. No lingering copies.</span>
                </li>
                <li className="flex gap-3">
                  <span className="text-[#D97745] mt-1">→</span>
                  <span><strong className="text-white">Built with security-first principles.</strong> We follow SOC 2 security practices from day one, including audit logs, strict data isolation, and regular security reviews.</span>
                </li>
              </ul>
              <p className="text-white/50 text-sm italic border-t border-white/10 pt-6 mt-6">
                You don’t have to start with your executive’s inbox. Many assistants begin by connecting their own email first and switch over when they’re comfortable.
              </p>
            </div>
          </div>
        </div>
      </section>



      {/* Application Form */}
      <section id="apply" className="py-24 bg-gradient-to-b from-[#111111] to-[#0a0a0a]">
        <div className="max-w-lg mx-auto px-6 lg:px-8">
          <div className="text-center mb-10">
            <h2 className="font-serif text-3xl sm:text-4xl text-white mb-4">
              Request Founding Access
            </h2>
          </div>

          {formState.submitted ? (
            <div className="p-10 rounded-2xl bg-[#161616] border border-[#7E2E2E]/20 text-center">
              <div className="w-12 h-12 rounded-full bg-[#7E2E2E]/10 flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-[#7E2E2E]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="font-serif text-2xl text-white mb-2">Thanks for applying, {formState.name.split(' ')[0]}.</h3>
              <p className="text-white/50">
                We'll review your application and get back to you within 24 hours.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-xs uppercase tracking-widest text-white/40 mb-2">Full Name</label>
                <input
                  type="text"
                  required
                  className="w-full px-5 py-4 rounded-xl bg-[#161616] border border-white/[0.08] text-white placeholder-white/20 focus:outline-none focus:border-[#7E2E2E]/50 focus:ring-1 focus:ring-[#7E2E2E]/20 transition-all"
                  placeholder="Your name"
                  value={formState.name}
                  onChange={(e) => setFormState({ ...formState, name: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-widest text-white/40 mb-2">Work Email</label>
                <input
                  type="email"
                  required
                  className="w-full px-5 py-4 rounded-xl bg-[#161616] border border-white/[0.08] text-white placeholder-white/20 focus:outline-none focus:border-[#7E2E2E]/50 focus:ring-1 focus:ring-[#7E2E2E]/20 transition-all"
                  placeholder="you@company.com"
                  value={formState.email}
                  onChange={(e) => setFormState({ ...formState, email: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-widest text-white/40 mb-2">LinkedIn Profile</label>
                <input
                  type="url"
                  required
                  className="w-full px-5 py-4 rounded-xl bg-[#161616] border border-white/[0.08] text-white placeholder-white/20 focus:outline-none focus:border-[#7E2E2E]/50 focus:ring-1 focus:ring-[#7E2E2E]/20 transition-all"
                  placeholder="linkedin.com/in/yourprofile"
                  value={formState.linkedin}
                  onChange={(e) => setFormState({ ...formState, linkedin: e.target.value })}
                />
              </div>
              <button
                type="submit"
                disabled={formState.submitting}
                className="w-full py-4 rounded-xl bg-[#7E2E2E] text-[#F9F6F2] font-medium hover:bg-[#8B3A3A] transition-colors mt-2 disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {formState.submitting ? (
                  <>
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Submitting...
                  </>
                ) : (
                  'Submit Application'
                )}
              </button>
              <p className="text-center text-white/30 text-xs mt-4">
                We respect your privacy. Your information is never shared.
              </p>
            </form>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <img src="/teeks-logo-gold.svg" alt="Teeks Symbol" className="w-6 h-6" />
            <span className="text-white/60 text-sm">Teeks</span>
          </div>
          <p className="text-white/30 text-xs">
            © 2026 Teeks Intelligence. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
};

const FeatureCarousel = () => {
  const [currentSet, setCurrentSet] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused) return;
    const timer = setInterval(() => {
      setCurrentSet(prev => (prev === 0 ? 1 : 0));
    }, 3000);
    return () => clearInterval(timer);
  }, [isPaused]);

  const features = [
    // Set 1
    [
      {
        id: '01',
        subtitle: 'Main Difference',
        title: 'Executive Context Engine',
        desc: "Teeks learns how your executive operates. It understands how they sign off emails, when they prefer meetings, who gets priority, and what “urgent” actually means to them.",
        note: 'Other tools: Learn your habits but miss what your executive needs.',
        colSpan: 'lg:col-span-2'
      },
      {
        id: '02',
        subtitle: 'Philosophy',
        title: 'Suggest → Act',
        desc: "Teeks never auto-sends. Never auto-changes. Never acts without your explicit approval (unless you allow it). Every suggestion is visible. Every action is explainable.",
        colSpan: ''
      },
      {
        id: '03',
        subtitle: 'Memory',
        title: 'Thread Intelligence',
        desc: '"Sarah approved the budget on January 15th." Teeks tracks decisions, commitments, and context within each conversation. When a conversation resurfaces weeks later, you have all the context ready.',
        colSpan: 'lg:col-span-3'
      }
    ],
    // Set 2
    [
      {
        id: '04',
        subtitle: 'Learning',
        title: 'Decision Patterns',
        desc: 'Teeks remembers your decisions and preferences and applies them when handling future tasks.',
        colSpan: 'lg:col-span-2'
      },
      {
        id: '05',
        subtitle: 'Relationships',
        title: 'Contact Context',
        desc: '"Mark Sarah as VIP—always formal." Teeks remembers communication preferences and urgency levels for every contact, so you do not have to brief it every time.',
        colSpan: ''
      },
      {
        id: '06',
        subtitle: 'Architecture',
        title: 'Executive-Executive Assistant relationship',
        desc: "Teeks is built specifically for the Executive-Executive Assistant relationship, allowing you to speak, decide, and act as your executive while keeping your own judgment and control intact.",
        colSpan: 'lg:col-span-3'
      }
    ]
  ];

  return (
    <div
      className="relative"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      <div className="relative min-h-[400px]">
        {features.map((set, setIndex) => (
          <div
            key={setIndex}
            className={`absolute inset-0 transition-all duration-700 ease-in-out transform ${currentSet === setIndex
              ? 'opacity-100 translate-x-0 z-10'
              : 'opacity-0 translate-x-4 z-0'
              }`}
          >
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {set.map((feature, idx) => (
                <div
                  key={feature.id}
                  className={`group p-8 rounded-2xl bg-[#161616] border border-white/[0.06] hover:border-white/[0.12] transition-all bg-gradient-to-b from-white/[0.02] to-transparent ${feature.colSpan}`}
                >
                  <div className="flex items-start justify-between mb-6">
                    <span className="text-[#D97745]/60 text-xs font-medium uppercase tracking-wider">{feature.subtitle}</span>
                    <span className="font-serif text-4xl text-white/[0.06] group-hover:text-white/[0.1] transition-colors">{feature.id}</span>
                  </div>
                  <h3 className="font-serif text-xl text-white mb-3">{feature.title}</h3>
                  <p className="text-white/50 text-sm leading-relaxed mb-4">
                    {feature.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="flex justify-center items-center gap-6 mt-12 z-20 relative">
        <div className="flex gap-2">
          {[0, 1].map((idx) => (
            <button
              key={idx}
              onClick={() => setCurrentSet(idx)}
              className={`h-1.5 rounded-full transition-all duration-300 ${currentSet === idx ? 'w-8 bg-[#D97745]' : 'w-1.5 bg-white/20 hover:bg-white/40'
                }`}
            />
          ))}
        </div>

        <button
          onClick={() => setCurrentSet(prev => (prev === 0 ? 1 : 0))}
          className="text-white/40 hover:text-white transition-colors"
        >
          <span className="sr-only">Next</span>
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 8l4 4m0 0l-4 4m4-4H3" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default App;
