import React, { useState } from 'react';
import { Send, Bookmark, Check } from 'lucide-react';
import { useStore } from '../store';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';


export const ChatView: React.FC = () => {
  const { chatHistory, addMessage, clearHistory } = useStore();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set());

  // Add the save function
  const handleSaveExploration = async (msgIndex: number, answer: string, sources?: string[]) => {
    // Grab the user's question (it should be the message immediately before the assistant's)
    const question = chatHistory[msgIndex - 1]?.content || "Saved Exploration";
    
    setSavingId(msgIndex);
    
    try {
      const response = await fetch('http://localhost:8000/save-exploration', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: question,
          answer: answer,
          sources: sources || []
        }),
      });

      if (!response.ok) throw new Error("Failed to save");
      
      // Mark as permanently saved for this session
      setSavedIds(prev => new Set(prev).add(msgIndex));
    } catch (error) {
      console.error("Error saving exploration:", error);
      alert("Failed to save to knowledge base.");
    } finally {
      setSavingId(null);
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = input.trim();
    setInput('');
    clearHistory();
    addMessage({ role: 'user', content: userMessage });
    setIsLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/ask', {
        question: userMessage
      });

      addMessage({ 
        role: 'assistant', 
        content: response.data.answer,
        sources: response.data.sources 
      });
    } catch (error) {
      console.error('Chat failed:', error);
      addMessage({ role: 'assistant', content: 'Sorry, I encountered an error researching that.' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white max-w-4xl mx-auto w-full border-x border-slate-200">
      {/* Chat History */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {chatHistory.length === 0 ? (
          <div className="text-center text-slate-400 mt-20">
            Ask the Librarian a question about your documents.
          </div>
        ) : (
          chatHistory.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-lg p-4 ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-800'}`}>
                {/* Move the text-sizing classes to a wrapper div */}
                <div className="text-sm md:text-base">
                    <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                        // Style headers
                        h1: ({node, ...props}) => <h1 className="text-xl font-bold mt-4 mb-2" {...props} />,
                        h2: ({node, ...props}) => <h2 className="text-lg font-bold mt-4 mb-2" {...props} />,
                        h3: ({node, ...props}) => <h3 className="text-md font-bold mt-3 mb-1" {...props} />,
                        // Style paragraphs with better line-height for reading
                        p: ({node, ...props}) => <p className="mb-3 leading-relaxed last:mb-0" {...props} />,
                        // Style lists
                        ul: ({node, ...props}) => <ul className="list-disc list-outside ml-5 mb-3 space-y-1" {...props} />,
                        ol: ({node, ...props}) => <ol className="list-decimal list-outside ml-5 mb-3 space-y-1" {...props} />,
                        // Style inline code and code blocks
                        code: ({node, inline, className, children, ...props}: any) => {
                        return inline ? (
                            <code className="bg-black/10 rounded px-1.5 py-0.5 text-sm font-mono" {...props}>
                            {children}
                            </code>
                        ) : (
                            <div className="bg-slate-800 text-slate-100 rounded-md p-3 my-3 overflow-x-auto text-sm font-mono shadow-sm">
                            <code {...props}>{children}</code>
                            </div>
                        );
                        },
                        // Style bold text
                        strong: ({node, ...props}) => <strong className="font-semibold" {...props} />
                    }}
                    >
                    {msg.content}
                    </ReactMarkdown>
                </div>
                
                {/* Render Sources if they exist */}
                {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-300 text-sm">
                    <strong>Sources:</strong>
                    <ul className="list-disc list-inside mt-1">
                        {msg.sources.map((src, i) => (
                        <li key={i}>{src}</li>
                        ))}
                    </ul>
                    </div>
                )}
                {msg.role === 'assistant' && (
                    <div className="mt-4 flex justify-end">
                    <button
                        onClick={() => handleSaveExploration(idx, msg.content, msg.sources)}
                        disabled={savedIds.has(idx) || savingId === idx}
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                        savedIds.has(idx) 
                            ? 'bg-green-100 text-green-700 cursor-default' 
                            : 'bg-white border border-slate-300 text-slate-600 hover:bg-slate-50 hover:text-blue-600'
                        }`}
                    >
                        {savedIds.has(idx) ? (
                        <>
                            <Check size={14} />
                            Saved to Wiki
                        </>
                        ) : (
                        <>
                            <Bookmark size={14} />
                            {savingId === idx ? 'Saving...' : 'Save Exploration'}
                        </>
                        )}
                    </button>
                    </div>
                )}
                {/* ------------------------------------------- */}
                </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-slate-100 text-slate-500 rounded-lg p-4 animate-pulse">
              The Librarian is researching...
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-slate-200">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Search your knowledge base..."
            className="flex-1 px-4 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 text-white p-2 rounded-md hover:bg-blue-700 disabled:bg-blue-300 transition-colors"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  );
};