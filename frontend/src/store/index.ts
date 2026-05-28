import { create } from "zustand";
import type { User, InterviewSession, ChatMessage } from "@/types";

interface AppState {
  // 主题
  theme: "light" | "dark";
  toggleTheme: () => void;

  // 用户认证
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  logout: () => void;

  // 简历关键词
  keywords: string[];
  setKeywords: (keywords: string[]) => void;

  // 面试会话 ID（从后端 /api/interview/start 获取）
  sessionId: string | null;
  setSessionId: (id: string | null) => void;

  // 面试会话元数据
  session: InterviewSession | null;
  setSession: (session: InterviewSession | null) => void;

  // 对话历史
  messages: ChatMessage[];
  addMessage: (msg: ChatMessage) => void;
  clearMessages: () => void;

  // 面试流式状态（与 SSE 连接生命周期绑定）
  isStreaming: boolean;
  setStreaming: (v: boolean) => void;

  // 重置面试状态（离开面试间时调用）
  resetInterview: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  theme: "light",
  toggleTheme: () =>
    set((s) => ({
      theme: s.theme === "light" ? "dark" : "light",
    })),

  user: null,
  token: null,
  setAuth: (user, token) =>
    set({
      user,
      token,
      keywords: [],
      sessionId: null,
      session: null,
      messages: [],
      isStreaming: false,
    }),
  logout: () =>
    set({
      user: null,
      token: null,
      keywords: [],
      sessionId: null,
      session: null,
      messages: [],
      isStreaming: false,
    }),

  keywords: [],
  setKeywords: (keywords) => set({ keywords }),

  sessionId: null,
  setSessionId: (sessionId) => set({ sessionId }),

  session: null,
  setSession: (session) => set({ session }),

  messages: [],
  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),
  clearMessages: () => set({ messages: [] }),

  isStreaming: false,
  setStreaming: (isStreaming) => set({ isStreaming }),

  resetInterview: () =>
    set({
      sessionId: null,
      session: null,
      messages: [],
      isStreaming: false,
    }),
}));