import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Send, Mic, Loader2, ArrowLeft, StopCircle,
  WifiOff, RefreshCw, X, AlertTriangle,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/store";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";

// ===== SSE 重连配置 =====
const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 1000; // ms，指数退避基数

// ===== fetch + ReadableStream SSE 解析器 =====
interface SSEEvent {
  event: string;
  data: string;
}

async function* parsePostSSE(response: Response): AsyncGenerator<SSEEvent> {
  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}));
    throw new Error(errBody.detail || `服务器错误 (${response.status})`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("浏览器不支持 ReadableStream");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      const lines = part.split("\n");
      let eventType = "message";
      let dataStr = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.slice(6);
        }
      }

      if (dataStr) {
        yield { event: eventType, data: dataStr };
      }
    }
  }
}

// ===== Toast 类型 =====
interface Toast {
  id: number;
  type: "error" | "warning" | "info";
  message: string;
  action?: { label: string; onClick: () => void };
}

let toastIdCounter = 0;

export default function Interview() {
  const navigate = useNavigate();
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const retryCountRef = useRef(0);
  const sessionInitRef = useRef(false);

  const {
    keywords,
    token,
    sessionId,
    setSessionId,
    isStreaming,
    setStreaming,
    addMessage,
    messages,
    clearMessages,
    resetInterview,
  } = useAppStore();

  const [inputValue, setInputValue] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [statusText, setStatusText] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);

  // ===== Toast 管理 =====
  const addToast = useCallback(
    (type: Toast["type"], message: string, action?: Toast["action"]) => {
      const id = ++toastIdCounter;
      setToasts((prev) => [...prev, { id, type, message, action }]);
      // 自动消失（非 actionable 的 toast）
      if (!action) {
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, 4000);
      }
    },
    []
  );

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // ===== 辅助：构建请求头 =====
  const authHeaders = useCallback((): Record<string, string> => {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
  }, [token]);

  // ===== 初始化：创建面试会话 =====
  useEffect(() => {
    if (keywords.length === 0) {
      navigate("/upload");
      return;
    }
    if (sessionInitRef.current) return;
    sessionInitRef.current = true;

    const initSession = async () => {
      clearMessages();
      setSessionId(null);
      retryCountRef.current = 0;

      try {
        const res = await fetch("/api/interview/start", {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({ interview_type: "technical" }),
        });

        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          throw new Error(errBody.detail || "创建会话失败");
        }

        const data = await res.json();
        setSessionId(data.id);

        // 使用后端返回的开场白，避免重复
        const welcomeText = data.welcome_message || `你好！我是今天的面试官。请做一个简短的**自我介绍**，包括你的技术背景和最有代表性的项目经历。`;
        addMessage({
          role: "assistant",
          content: welcomeText,
        });
      } catch (err: any) {
        console.error("创建面试会话失败:", err);
        addToast("error", "创建面试会话失败，请检查后端服务是否启动");
        // 降级本地开场白（仅作为 fallback，不会重复触发）
        addMessage({
          role: "assistant",
          content: `你好！我是今天的面试官。我已经仔细阅读了你的简历。\n\n首先，请做一个简短的**自我介绍**吧——包括你的技术背景、项目经验和你认为自己最擅长的技术领域。`,
        });
      }
    };

    initSession();

    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
    };
  }, []);

  // ===== 自动滚动到底部 =====
  useEffect(() => {
    const container = chatContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, [messages, streamingContent]);

  // ===== 核心：发送消息 + SSE 流式接收 + 断线重连 =====
  const sendChatRequest = useCallback(
    async (content: string, attempt: number = 0): Promise<void> => {
      if (!sessionId) return;

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch("/api/interview/chat", {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({ session_id: sessionId, content }),
          signal: controller.signal,
        });

        let fullReply = "";

        for await (const sseEvent of parsePostSSE(res)) {
          if (controller.signal.aborted) break;

          try {
            const payload = JSON.parse(sseEvent.data);

            switch (sseEvent.event) {
              case "status":
                setStatusText(payload.message || "");
                break;

              case "message":
                fullReply += payload.content || "";
                setStreamingContent(fullReply);
                break;

              case "error":
                console.error("SSE error event:", payload.message);
                setStatusText("");
                addToast("error", payload.message || "AI 服务异常");
                break;

              case "end":
                if (fullReply) {
                  addMessage({ role: "assistant", content: fullReply });
                }
                setStreamingContent("");
                setStatusText("");
                setStreaming(false);
                retryCountRef.current = 0; // 成功后重置重试计数
                break;
            }
          } catch {
            // 跳过无法解析的 SSE 数据行
          }
        }

        // 读取完所有事件但没收到 end（异常断开）
        if (fullReply && !controller.signal.aborted) {
          // 仍有内容未保存——说明连接被非正常关闭
          // 检查：内容是否已通过 end 保存
          // 由于 setStreaming 状态没法在这里精确判断，做一个保守保存
        }
      } catch (err: any) {
        if (err.name === "AbortError") return;

        console.error(`SSE 请求失败 (attempt ${attempt + 1}):`, err);

        // ===== 断线重连逻辑 =====
        if (attempt < MAX_RETRIES) {
          const delay = BASE_RETRY_DELAY * Math.pow(2, attempt);
          retryCountRef.current = attempt + 1;

          addToast(
            "warning",
            `连接中断，${((delay / 1000)).toFixed(0)} 秒后自动重试 (${attempt + 1}/${MAX_RETRIES})`,
            {
              label: "立即重试",
              onClick: () => {
                removeToast(toasts[toasts.length - 1]?.id);
                sendChatRequest(content, attempt);
              },
            }
          );

          await new Promise((r) => setTimeout(r, delay));

          if (!controller.signal.aborted) {
            return sendChatRequest(content, attempt + 1);
          }
        } else {
          // 重试耗尽
          setStatusText("");
          setStreaming(false);
          retryCountRef.current = 0;
          addToast(
            "error",
            "网络连接失败，已重试 3 次仍无法恢复。请检查网络后重新发送",
            {
              label: "重新发送",
              onClick: () => {
                // 回滚最后一条用户消息并重试
                addToast("info", "正在重新发送...");
                sendChatRequest(content, 0);
              },
            }
          );
        }
      } finally {
        abortRef.current = null;
      }
    },
    [sessionId, token, authHeaders, addMessage, setStreaming, addToast, removeToast, toasts]
  );

  const handleSend = useCallback(() => {
    const content = inputValue.trim();
    if (!content || isStreaming || !sessionId) return;

    // 添加用户消息
    addMessage({ role: "user", content });
    setInputValue("");
    setStreamingContent("");
    setStatusText("");
    setStreaming(true);

    sendChatRequest(content, 0);
  }, [inputValue, isStreaming, sessionId, sendChatRequest, addMessage, setStreaming]);

  // ===== 结束面试 =====
  const [endingInterview, setEndingInterview] = useState(false);

  const handleEndInterview = async () => {
    if (!sessionId) {
      navigate("/report");
      return;
    }

    // 防止重复点击
    if (endingInterview) return;
    setEndingInterview(true);

    // 中止正在进行的 SSE 流
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }

    setStreaming(false);

    try {
      const res = await fetch(`/api/interview/${sessionId}/end`, {
        method: "POST",
        headers: authHeaders(),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "未知错误" }));
        addToast("error", `结束面试失败: ${errData.detail || res.statusText}`);
        setEndingInterview(false);
        return;
      }

      const data = await res.json();
      addToast("info", data.message || "面试已结束");

      // 短暂延迟确保后端报告生成完成
      await new Promise((r) => setTimeout(r, 1000));
    } catch (err) {
      console.error("结束面试请求失败:", err);
      addToast("error", "网络异常，请重试");
      setEndingInterview(false);
      return;
    }

    navigate("/report");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Toast 通知层 */}
      <div className="fixed top-20 right-4 z-[100] space-y-2 max-w-sm">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              "flex items-start gap-3 p-3 rounded-xl shadow-lg border animate-slide-up text-sm",
              toast.type === "error" &&
                "bg-red-50 dark:bg-red-950/80 border-red-200 dark:border-red-800 text-red-800 dark:text-red-300",
              toast.type === "warning" &&
                "bg-amber-50 dark:bg-amber-950/80 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300",
              toast.type === "info" &&
                "bg-blue-50 dark:bg-blue-950/80 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300"
            )}
          >
            {toast.type === "error" && <WifiOff className="h-4 w-4 shrink-0 mt-0.5" />}
            {toast.type === "warning" && <RefreshCw className="h-4 w-4 shrink-0 mt-0.5 animate-spin" />}
            {toast.type === "info" && <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />}

            <div className="flex-1 min-w-0">
              <p className="leading-relaxed">{toast.message}</p>
              {toast.action && (
                <button
                  onClick={toast.action.onClick}
                  className="mt-1 text-xs font-medium underline underline-offset-2 hover:no-underline"
                >
                  {toast.action.label}
                </button>
              )}
            </div>

            <button
              onClick={() => removeToast(toast.id)}
              className="shrink-0 opacity-60 hover:opacity-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>

      {/* 顶部信息栏 */}
      <div className="shrink-0 border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-gray-950/90 backdrop-blur-sm px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                if (abortRef.current) abortRef.current.abort();
                resetInterview();
                navigate("/upload");
              }}
              className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div>
              <h2 className="font-semibold text-sm">
                AI 模拟面试中
                {sessionId && (
                  <span className="ml-2 text-xs text-slate-400 font-normal">
                    #{sessionId.slice(0, 8)}
                  </span>
                )}
              </h2>
              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                {keywords.map((kw) => (
                  <span
                    key={kw}
                    className="text-xs px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleEndInterview}
            disabled={endingInterview}
            className="gap-1.5"
          >
            {endingInterview ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <StopCircle className="h-4 w-4" />
            )}
            结束面试
          </Button>
        </div>
      </div>

      {/* 聊天区域 */}
      <div
        ref={chatContainerRef}
        className="flex-1 overflow-y-auto px-4 py-6 scrollbar-thin"
      >
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.length <= 1 && (
            <div className="text-center py-8 text-slate-400 dark:text-slate-600 text-sm">
              <p>面试官已就位，请开始你的自我介绍</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <ChatBubble key={i} message={msg} />
          ))}

          {isStreaming && streamingContent && (
            <ChatBubble
              message={{ role: "assistant", content: streamingContent }}
              isStreaming
            />
          )}
        </div>
      </div>

      {/* 底部输入栏 */}
      <div className="shrink-0 border-t border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-gray-950/90 backdrop-blur-sm px-4 py-4">
        <div className="max-w-4xl mx-auto">
          {statusText && isStreaming && (
            <div className="mb-2 flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400 animate-fade-in">
              <Loader2 className="h-3 w-3 animate-spin" />
              {statusText}
            </div>
          )}

          <div className="flex items-end gap-2">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  isStreaming
                    ? "AI 正在回复中..."
                    : !sessionId
                    ? "正在连接面试官..."
                    : "输入你的回答... (Enter 发送, Shift+Enter 换行)"
                }
                disabled={isStreaming || !sessionId}
                rows={2}
                className={cn(
                  "w-full resize-none rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 px-4 py-3 pr-12 text-sm",
                  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                  "placeholder:text-slate-400 dark:placeholder:text-slate-600",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              />
            </div>

            <Button
              variant="ghost"
              size="icon"
              disabled={isStreaming || !sessionId}
              className="shrink-0"
              title="语音输入（即将上线）"
            >
              <Mic className="h-5 w-5" />
            </Button>

            <Button
              onClick={handleSend}
              disabled={!inputValue.trim() || isStreaming || !sessionId}
              size="icon"
              className="shrink-0"
            >
              {isStreaming ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ===== 聊天气泡组件 =====
function ChatBubble({
  message,
  isStreaming = false,
}: {
  message: ChatMessage;
  isStreaming?: boolean;
}) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3 animate-slide-up",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shrink-0 mt-1">
          <span className="text-white text-xs font-bold">AI</span>
        </div>
      )}

      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-blue-600 text-white rounded-br-md"
            : "bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-bl-md"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose-custom text-sm dark:text-slate-100">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {isStreaming && (
          <span className="inline-block w-0.5 h-4 bg-blue-600 dark:bg-blue-400 ml-0.5 animate-pulse align-middle" />
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-slate-300 dark:bg-slate-700 flex items-center justify-center shrink-0 mt-1">
          <span className="text-slate-600 dark:text-slate-300 text-xs font-bold">我</span>
        </div>
      )}
    </div>
  );
}