import React from 'react';
import { Network, MessageSquare, Book } from 'lucide-react';
import { useStore } from './store';
import { ResearchView } from './components/ResearchView';
import { ChatView } from './components/ChatView';
import { Dashboard } from './components/Dashboard'

function App() {
  const { activeTab, setActiveTab } = useStore();

  return (
    <div className="flex h-screen w-screen bg-slate-100 text-slate-900 overflow-hidden">
      {/* Sidebar / Navigation */}
      <div className="w-16 bg-slate-900 flex flex-col items-center py-6 gap-6 z-20 shadow-xl">
        <button
          onClick={() => setActiveTab('research')}
          className={`p-3 rounded-xl transition-all ${
            activeTab === 'research' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
          title="Research Graph"
        >
          <Network size={24} />
        </button>
        
        <button
          onClick={() => setActiveTab('chat')}
          className={`p-3 rounded-xl transition-all ${
            activeTab === 'chat' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
          title="Chat Assistant"
        >
          <MessageSquare size={24} />
        </button>

        <button
          onClick={() => setActiveTab('dash')}
          className={`p-3 rounded-xl transition-all ${
            activeTab === 'dash' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
          title="Dash"
        >
          <Book size={24} />
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 h-full relative">
        {(() => {
          switch (activeTab) {
            case 'research': return <ResearchView />;
            case 'dash': return <Dashboard />;
            default: return <ChatView />;
          }
        })()}
      </div>
    </div>
  );
}

export default App;