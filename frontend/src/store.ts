import { create } from 'zustand';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
}

interface GraphData {
  nodes: { id: string; name: string; val: number }[];
  links: { source: string; target: string }[];
}

interface GlobalState {
  activeTab: 'research' | 'chat' | 'dash';
  isProcessing: boolean;
  chatHistory: Message[];
  graphData: GraphData;
  setActiveTab: (tab: 'research' | 'chat' | 'dash') => void;
  setIsProcessing: (status: boolean) => void;
  addMessage: (msg: Message) => void;
  clearHistory: () => void;
  setGraphData: (data: GraphData) => void;
}

export const useStore = create<GlobalState>((set) => ({
  activeTab: 'research',
  isProcessing: false,
  chatHistory: [],
  graphData: { nodes: [], links: [] },
  setActiveTab: (tab) => set({ activeTab: tab }),
  setIsProcessing: (status) => set({ isProcessing: status }),
  addMessage: (msg) => set((state) => ({ chatHistory: [...state.chatHistory, msg] })),
  clearHistory: () => set({ chatHistory: [] }),
  setGraphData: (data) => set({ graphData: data }),
}));