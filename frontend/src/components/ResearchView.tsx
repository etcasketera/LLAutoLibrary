import React, { useRef, useEffect, useState, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { UploadCloud, X, RefreshCw } from 'lucide-react';
import { useStore } from '../store';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';


export const ResearchView: React.FC = () => {
  const { isProcessing, setIsProcessing, graphData, setGraphData } = useStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // State for the Side Panel
  const [selectedPanel, setSelectedPanel] = useState<{title: string, content: string, type: string} | null>(null);

  // Single function to fetch graph data
  const fetchGraph = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/graph-data');
      if (response.ok) {
        const data = await response.json();
        setGraphData(data);
      }
    } catch (error) {
      console.error("Failed to fetch graph data:", error);
    }
  }, [setGraphData]);

  // Fetch only ONCE when the component mounts
  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      
      alert(`${file.name} sent to Librarian for processing. Click the Refresh Graph button in a few seconds.`);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to upload file.');
    } finally {
      setIsProcessing(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Node Click Handler
  const handleNodeClick = async (node: any) => {
    try {
      // Encode the ID so files with spaces or symbols in their names don't break the URL
      const encodedId = encodeURIComponent(node.id);
      const response = await fetch(`http://localhost:8000/file/${encodedId}`);
      if (response.ok) {
        const data = await response.json();
        console.log("Data received from backend:", data);
        setSelectedPanel(data);
      } else {
        alert("Could not load file contents.");
      }
    } catch (error) {
      console.error("Error fetching file:", error);
    }
  };

  return (
    <div className="w-full h-full flex relative bg-slate-50">
      
      {/* Top Left Controls */}
      <div className="absolute top-4 left-4 z-10 flex gap-2">
        <div className="bg-white p-4 rounded-lg shadow-md border border-slate-200">
          <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" />
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isProcessing}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:bg-blue-300 transition-colors"
          >
            <UploadCloud size={20} />
            {isProcessing ? 'Processing Document...' : 'Upload Raw File'}
          </button>
        </div>
        
        {/* Manual Refresh Button */}
        <button 
          onClick={fetchGraph}
          className="bg-white p-4 rounded-lg shadow-md border border-slate-200 text-slate-600 hover:text-blue-600 transition-colors"
          title="Refresh Graph"
        >
          <RefreshCw size={24} />
        </button>
      </div>

      {/* Main Graph Canvas */}
      <div className="flex-1 overflow-hidden cursor-move">
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            graphData={graphData}
            nodeAutoColorBy="group"
            nodeLabel="name"
            onNodeClick={handleNodeClick}
            // linkDirectionalParticles={2}
            // linkDirectionalParticleSpeed={0.005}
            linkColor={() => 'rgba(255, 255, 255, 0.4)'} // Makes the lines a soft white
            linkWidth={1.5} // Makes the lines slightly thicker
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-400">
            Upload files to generate the concept graph.
          </div>
        )}
      </div>

      {/* Inspector Side Panel */}
      {selectedPanel && (
        <div className="absolute top-0 right-0 w-96 h-full bg-white shadow-2xl border-l border-slate-200 flex flex-col z-[100] animate-in slide-in-from-right-8 duration-200">
          
          <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
            {/* Added overflow-hidden here to ensure long titles don't push the X button out */}
            <div className="overflow-hidden">
              <span className="text-xs font-bold text-blue-600 uppercase tracking-wider">{selectedPanel.type}</span>
              <h2 className="text-lg font-semibold truncate pr-4" title={selectedPanel.title}>
                {selectedPanel.title}
              </h2>
            </div>
            <button 
              onClick={() => setSelectedPanel(null)} 
              className="text-slate-400 hover:text-slate-800 shrink-0"
            >
              <X size={24} />
            </button>
          </div>

          <div className="p-6 flex-1 overflow-y-auto">
            <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                h1: ({node, ...props}) => <h1 className="text-xl font-bold mb-4" {...props} />,
                p: ({node, ...props}) => <p className="mb-3 text-slate-700 leading-relaxed" {...props} />,
                li: ({node, ...props}) => <li className="mb-1" {...props} />,
                // Ensure [[Links]] are highlighted
                text: ({node, ...props}) => {
                    const content = props.children as string;
                    if (content?.includes('[[')) {
                    return <span className="text-blue-600 font-medium">{content}</span>;
                    }
                    return <>{content}</>;
                }
                }}
            >
                {selectedPanel.content}
            </ReactMarkdown>
          </div>
          
        </div>
      )}

    </div>
  );
};