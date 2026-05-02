import { create } from 'zustand';

const STORAGE_KEY = 'current_workspace_id';

export const useWorkspaceStore = create((set) => ({
  currentWorkspaceId: localStorage.getItem(STORAGE_KEY) || null,
  workspaces: [],
  channels: [],

  setCurrentWorkspace: (id) => {
    localStorage.setItem(STORAGE_KEY, id);
    set({ currentWorkspaceId: id });
  },
  setWorkspaces: (workspaces) => set({ workspaces }),
  setChannels: (channels) => set({ channels }),
}));
