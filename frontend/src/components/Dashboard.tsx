import React, { useEffect, useState } from 'react';
import { useStore } from '../store'; 

export const Dashboard: React.FC = () => {
    const [data, setData] = useState<any>(null);
    const [search, setSearch] = useState("");

    useEffect(() => {
        fetch("http://localhost:8000/dashboard-summary")
            .then(res => res.json())
            .then(setData);
    }, []);

    const handleQuickSearch = (e: React.FormEvent) => {
        e.preventDefault();
        // Trigger the global research 'ask' logic
        window.location.hash = `#/research?q=${encodeURIComponent(search)}`;
    };

    if (!data) return <div className="p-8">Loading Librarian Dashboard...</div>;

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-8">
            {/* Header & Global Search */}
            <div className="text-center space-y-4">
                <h1 className="text-4xl font-bold">LLLibrary Dashboard</h1>
                <form onSubmit={handleQuickSearch} className="max-w-2xl mx-auto">
                    <input 
                        type="text" 
                        placeholder="Search your knowledge graph..."
                        className="w-full p-4 rounded-full border-2 border-blue-500 shadow-lg"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </form>
            </div>

            {/* Stats Overview */}
            <div className="grid grid-cols-3 gap-6">
                <div className="p-6 bg-blue-50 rounded-xl shadow">
                    <p className="text-sm text-blue-600 font-semibold">Total Sources</p>
                    <p className="text-3xl font-bold">{data.stats.total_sources}</p>
                </div>
                <div className="p-6 bg-green-50 rounded-xl shadow">
                    <p className="text-sm text-green-600 font-semibold">Unique Concepts</p>
                    <p className="text-3xl font-bold">{data.stats.total_concepts}</p>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-8">
                {/* Recent Activity Card */}
                <div className="bg-white p-6 rounded-xl border shadow-sm">
                    <h2 className="text-xl font-bold mb-4">Recent Research</h2>
                    {data.recent_activity.map((item: any) => (
                        <div key={item.name} className="flex justify-between items-center py-2 border-b">
                            <span>{item.name}</span>
                            <span className="px-2 py-1 bg-gray-100 rounded text-xs">Rank: {item.importance}</span>
                        </div>
                    ))}
                </div>

                {/* Top Concepts Card */}
                <div className="bg-white p-6 rounded-xl border shadow-sm">
                    <h2 className="text-xl font-bold mb-4">Knowledge Pillars</h2>
                    <div className="flex flex-wrap gap-2">
                        {data.top_concepts.map((concept: any) => (
                            <button 
                                key={concept.name}
                                className="px-4 py-2 bg-blue-100 text-blue-800 rounded-full hover:bg-blue-200 transition"
                            >
                                {concept.name} ({concept.connections})
                            </button>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};