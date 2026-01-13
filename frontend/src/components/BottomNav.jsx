import React from 'react';
import { Mail, CheckSquare, Calendar, Settings, MessageCircle } from 'lucide-react';

const NavButton = ({ active, onClick, icon: Icon, label }) => (
    <button
        onClick={onClick}
        className={`flex flex-col items-center gap-1 p-2 min-w-[56px] transition-colors ${active ? 'text-blue-600' : 'text-gray-400 hover:text-gray-600'
            }`}
    >
        <Icon className={`w-5 h-5 ${active ? 'fill-blue-100' : ''}`} />
        <span className="text-[10px] font-medium">{label}</span>
    </button>
);

const BottomNav = ({ currentView, onNavigate }) => (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-2 flex justify-around items-center z-50 pb-safe">
        <NavButton
            active={currentView === 'dashboard' || currentView === 'detail' || currentView === 'draft'}
            onClick={() => onNavigate('dashboard')}
            icon={Mail}
            label="Inbox"
        />
        <NavButton
            active={currentView === 'tasks'}
            onClick={() => onNavigate('tasks')}
            icon={CheckSquare}
            label="Tasks"
        />
        <NavButton
            active={currentView === 'chat'}
            onClick={() => onNavigate('chat')}
            icon={MessageCircle}
            label="Chat"
        />
        <NavButton
            active={currentView === 'calendar'}
            onClick={() => onNavigate('calendar')}
            icon={Calendar}
            label="Calendar"
        />
        <NavButton
            active={currentView === 'settings'}
            onClick={() => onNavigate('settings')}
            icon={Settings}
            label="Settings"
        />
    </div>
);

export default BottomNav;
