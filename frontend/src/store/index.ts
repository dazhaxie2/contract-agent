import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AuthState {
  token: string | null;
  refreshToken: string | null;
  tenantId: string;
  userId: string;
  isAuthenticated: boolean;
  login: (token: string, refreshToken: string, tenantId: string, userId?: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      tenantId: 'default',
      userId: '',
      isAuthenticated: false,
      login: (token, refreshToken, tenantId, userId = '') => {
        localStorage.setItem('access_token', token);
        localStorage.setItem('refresh_token', refreshToken);
        localStorage.setItem('tenant_id', tenantId);
        set({ token, refreshToken, tenantId, userId, isAuthenticated: true });
      },
      logout: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('tenant_id');
        set({ token: null, refreshToken: null, tenantId: 'default', userId: '', isAuthenticated: false });
      },
    }),
    { name: 'auth-storage' },
  ),
);

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  references?: Record<string, unknown>[];
  timestamp: number;
  streaming?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
}

interface ChatState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  activeSession: () => ChatSession | undefined;
  createSession: (id: string, title: string) => void;
  setActiveSession: (id: string) => void;
  addMessage: (sessionId: string, message: ChatMessage) => void;
  updateMessage: (sessionId: string, messageId: string, updates: Partial<ChatMessage>) => void;
  appendMessageContent: (sessionId: string, messageId: string, text: string) => void;
  clearSessions: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeSessionId: null,
      activeSession: () => {
        const state = get();
        return state.sessions.find((s) => s.id === state.activeSessionId);
      },
      createSession: (id, title) =>
        set((state) => {
          if (state.sessions.some((s) => s.id === id)) {
            return { activeSessionId: id };
          }
          return {
            sessions: [...state.sessions, { id, title, messages: [] }],
            activeSessionId: id,
          };
        }),
      setActiveSession: (id) => set({ activeSessionId: id }),
      addMessage: (sessionId, message) =>
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId ? { ...s, messages: [...s.messages, message] } : s,
          ),
        })),
      updateMessage: (sessionId, messageId, updates) =>
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? { ...s, messages: s.messages.map((m) => (m.id === messageId ? { ...m, ...updates } : m)) }
              : s,
          ),
        })),
      appendMessageContent: (sessionId, messageId, text) =>
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? {
                  ...s,
                  messages: s.messages.map((m) =>
                    m.id === messageId ? { ...m, content: m.content + text } : m,
                  ),
                }
              : s,
          ),
        })),
      clearSessions: () => set({ sessions: [], activeSessionId: null }),
    }),
    { name: 'chat-storage', partialize: (state) => ({ sessions: state.sessions, activeSessionId: state.activeSessionId }) },
  ),
);

interface CacheState {
  embeddingCache: Record<string, number>;
  hit: (key: string) => number | undefined;
  set: (key: string, value: number) => void;
}

export const useCacheStore = create<CacheState>()((set, get) => ({
  embeddingCache: {},
  hit: (key) => get().embeddingCache[key],
  set: (key, value) =>
    set((state) => ({
      embeddingCache: { ...state.embeddingCache, [key]: value },
    })),
}));
