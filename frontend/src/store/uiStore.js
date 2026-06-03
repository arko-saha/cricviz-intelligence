import { create } from 'zustand';

const useUIStore = create((set) => ({
  // Active pillar
  activePillar: 'matches',
  setActivePillar: (pillar) => set({ activePillar: pillar }),

  // Selected entities
  selectedMatchId: null,
  setSelectedMatchId: (id) => set({ selectedMatchId: id }),
  selectedPlayerId: null,
  setSelectedPlayerId: (id) => set({ selectedPlayerId: id }),

  // AI sidebar
  aiPanelOpen: false,
  toggleAIPanel: () => set((s) => ({ aiPanelOpen: !s.aiPanelOpen })),
  setAIPanelOpen: (open) => set({ aiPanelOpen: open }),

  // AI context data (match or player data to send to Claude)
  aiContextData: null,
  aiContextType: 'match',
  setAIContext: (data, type = 'match') =>
    set({ aiContextData: data, aiContextType: type }),
}));

export default useUIStore;
