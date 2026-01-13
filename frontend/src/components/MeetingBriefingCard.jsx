import React from 'react';
import { Users, Calendar, AlertCircle, Mail, CheckCircle2, ChevronRight, Info } from 'lucide-react';

const MeetingBriefingCard = ({ briefing, onNavigateToDetail }) => {
    if (!briefing) return null;

    const {
        attendees = [],
        agenda = '',
        prep_warnings = [],
        related_emails = [],
        open_tasks = [],
        prep_complete = false
    } = briefing;

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden mb-6">
            {/* Prep Status Header */}
            <div className={`px-4 py-3 flex items-center justify-between ${prep_complete ? 'bg-green-50' : 'bg-amber-50'}`}>
                <div className="flex items-center gap-2">
                    {prep_complete ? (
                        <CheckCircle2 className="w-5 h-5 text-green-600" />
                    ) : (
                        <AlertCircle className="w-5 h-5 text-amber-600" />
                    )}
                    <span className={`text-sm font-semibold ${prep_complete ? 'text-green-700' : 'text-amber-700'}`}>
                        {prep_complete ? 'Prep Complete' : 'Needs Preparation'}
                    </span>
                </div>
                {!prep_complete && (
                    <span className="text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full font-medium">
                        {prep_warnings.length} Warning{prep_warnings.length !== 1 ? 's' : ''}
                    </span>
                )}
            </div>

            <div className="p-4 space-y-6">
                {/* Agenda */}
                <div>
                    <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <Info className="w-3 h-3" /> Agenda
                    </h3>
                    <p className="text-gray-700 text-sm leading-relaxed">
                        {agenda}
                    </p>
                </div>

                {/* Prep Warnings */}
                {prep_warnings.length > 0 && (
                    <div className="space-y-2">
                        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" /> Prep Warnings
                        </h3>
                        <div className="space-y-2">
                            {prep_warnings.map((warning, idx) => (
                                <div key={idx} className="flex gap-3 p-3 bg-red-50 rounded-xl border border-red-100">
                                    <div className={`mt-0.5 p-1 rounded-full ${warning.severity === 'high' ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'}`}>
                                        <AlertCircle className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-gray-900">{warning.message}</p>
                                        <p className="text-xs text-gray-500 mt-1">{warning.suggestion}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Attendees */}
                <div>
                    <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <Users className="w-3 h-3" /> Key Participants
                    </h3>
                    <div className="flex flex-wrap gap-2">
                        {attendees.map((person, idx) => (
                            <div key={idx} className="flex items-center gap-2 p-1.5 bg-gray-50 rounded-full border border-gray-100 pr-3">
                                <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-[10px] font-bold text-blue-600">
                                    {(person.name || person.email || '?')[0].toUpperCase()}
                                </div>
                                <span className="text-xs font-medium text-gray-700">{person.name || person.email}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Related Emails */}
                {related_emails.length > 0 && (
                    <div>
                        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                            <Mail className="w-3 h-3" /> Related Context
                        </h3>
                        <div className="space-y-2">
                            {related_emails.slice(0, 3).map((email, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => onNavigateToDetail(email.id)}
                                    className="w-full flex items-center justify-between p-3 bg-white border border-gray-100 rounded-xl hover:bg-gray-50 transition-colors text-left"
                                >
                                    <div className="flex-1 min-w-0 pr-4">
                                        <p className="text-sm font-medium text-gray-900 truncate">{email.subject}</p>
                                        <p className="text-xs text-gray-500 truncate mt-0.5">From {email.sender}</p>
                                    </div>
                                    <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Open Tasks */}
                {open_tasks.length > 0 && (
                    <div>
                        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Related Tasks
                        </h3>
                        <div className="space-y-2">
                            {open_tasks.map((task, idx) => (
                                <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
                                    <div className={`p-1 rounded-full ${task.priority === 'high' ? 'bg-orange-100 text-orange-600' : 'bg-blue-100 text-blue-600'}`}>
                                        <CheckCircle2 className="w-4 h-4" />
                                    </div>
                                    <span className="text-sm font-medium text-gray-700">{task.title}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default MeetingBriefingCard;
