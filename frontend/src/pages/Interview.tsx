import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Send, Loader2, ArrowLeft, StopCircle,
  WifiOff, RefreshCw, X, AlertTriangle,
  BriefcaseBusiness, ClipboardList, CheckCircle2,
  CircleDashed, Gauge, Copy, Check, ArrowDown,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/store";
import { cn } from "@/lib/utils";
import type { ChatMessage, InterviewType } from "@/types";

// ===== SSE 重连配置 =====
const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 1000; // ms，指数退避基数
const MAX_INTERVIEW_TURNS = 15;

const INTERVIEW_TYPE_LABELS: Record<InterviewType, string> = {
  technical: "基础技术面",
  pressure: "压力面试",
  friendly: "轻松聊天",
};

const JD_TOPIC_RULES = [
  { label: "项目架构", patterns: ["架构", "系统设计", "模块", "微服务", "分布式"] },
  { label: "性能优化", patterns: ["性能", "优化", "高并发", "响应时间", "吞吐"] },
  { label: "数据库", patterns: ["mysql", "postgresql", "数据库", "sql", "索引"] },
  { label: "缓存", patterns: ["redis", "缓存", "cache"] },
  { label: "部署运维", patterns: ["docker", "kubernetes", "k8s", "部署", "devops", "ci/cd"] },
  { label: "故障排查", patterns: ["排查", "故障", "监控", "日志", "告警"] },
  { label: "测试质量", patterns: ["测试", "单元测试", "质量", "review", "代码规范"] },
  { label: "团队协作", patterns: ["协作", "沟通", "团队", "跨部门", "需求"] },
];

const TOPIC_ALIASES: Record<string, string[]> = {
  项目架构: ["项目", "架构", "系统设计", "模块"],
  性能优化: ["性能", "优化", "高并发", "响应时间"],
  故障排查: ["故障", "排查", "日志", "监控", "异常"],
  沟通协作: ["沟通", "协作", "团队", "分歧"],
  部署运维: ["部署", "docker", "kubernetes", "k8s", "ci/cd"],
  测试质量: ["测试", "质量", "review", "代码规范"],
};

const ABILITY_BY_TURN = [
  { maxTurn: 1, ability: "逻辑表达", focus: "自我介绍与背景梳理" },
  { maxTurn: 3, ability: "专业知识广度", focus: "技术基础与概念准确性" },
  { maxTurn: 5, ability: "技术深度", focus: "原理机制与技术取舍" },
  { maxTurn: 8, ability: "项目实践能力", focus: "项目架构、落地和效果" },
  { maxTurn: 11, ability: "应变与解决问题能力", focus: "压力追问、边界条件和排障" },
  { maxTurn: 13, ability: "沟通与协作素养", focus: "团队协作与职业素养" },
  { maxTurn: 15, ability: "岗位匹配度", focus: "目标岗位动机与补强方向" },
];

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function normalizeText(value: string) {
  return value.toLowerCase().replace(/\s+/g, "");
}

function topicCovered(topic: string, normalizedDialogue: string) {
  const aliases = [topic, ...(TOPIC_ALIASES[topic] || [])];
  return aliases.some((alias) => normalizedDialogue.includes(normalizeText(alias)));
}

function buildInterviewTopics(keywords: string[], jobDescription: string, jobTitle: string) {
  const baseTopics = keywords.slice(0, 8);
  const jdText = normalizeText(`${jobTitle} ${jobDescription}`);
  const jdTopics = JD_TOPIC_RULES
    .filter((rule) => rule.patterns.some((pattern) => jdText.includes(normalizeText(pattern))))
    .map((rule) => rule.label);

  return unique([
    ...baseTopics,
    ...jdTopics,
    "项目架构",
    "性能优化",
    "故障排查",
    "沟通协作",
  ]).slice(0, 12);
}

function inferCurrentAbility(userTurnCount: number, lastAssistantContent: string) {
  const text = normalizeText(lastAssistantContent);

  if (/项目|架构|上线|部署|性能|优化|选型/.test(text)) {
    return { ability: "项目实践能力", focus: "项目落地、架构取舍和量化结果" };
  }
  if (/原理|底层|机制|源码|深入|为什么/.test(text)) {
    return { ability: "技术深度", focus: "原理机制、边界条件和技术取舍" };
  }
  if (/故障|排查|生产|压力|质疑|凌晨|异常|边界/.test(text)) {
    return { ability: "应变与解决问题能力", focus: "异常场景、排障路径和抗压表现" };
  }
  if (/团队|协作|沟通|分歧|同事|规划|加班/.test(text)) {
    return { ability: "沟通与协作素养", focus: "表达、协作和职业判断" };
  }

  return ABILITY_BY_TURN.find((item) => userTurnCount <= item.maxTurn) || ABILITY_BY_TURN[ABILITY_BY_TURN.length - 1];
}

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

interface InterviewProgress {
  userTurnCount: number;
  percent: number;
  currentAbility: string;
  currentFocus: string;
  coveredTopics: string[];
  pendingTopics: string[];
}

let toastIdCounter = 0;

export default function Interview() {
  const navigate = useNavigate();
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const textareaWrapperRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const retryCountRef = useRef(0);
  const sessionInitRef = useRef(false);
  // 拖拽 resize 状态
  const isResizingRef = useRef(false);
  const startDragYRef = useRef(0);
  const startHeightRef = useRef(0);

  const {
    keywords,
    jobTitle,
    jobDescription,
    interviewType,
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
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);

  const interviewProgress = useMemo<InterviewProgress>(() => {
    const userTurnCount = messages.filter((msg) => msg.role === "user").length;
    const lastAssistantMessage = [...messages]
      .reverse()
      .find((msg) => msg.role === "assistant")?.content || "";
    const topics = buildInterviewTopics(keywords, jobDescription, jobTitle);
    const dialogueAfterOpening = normalizeText(
      messages.slice(1).map((msg) => msg.content).join(" ")
    );
    const coveredTopics = topics.filter((topic) => topicCovered(topic, dialogueAfterOpening));
    const pendingTopics = topics.filter((topic) => !coveredTopics.includes(topic));
    const current = inferCurrentAbility(userTurnCount, streamingContent || lastAssistantMessage);

    return {
      userTurnCount,
      percent: Math.min(100, Math.round((userTurnCount / MAX_INTERVIEW_TURNS) * 100)),
      currentAbility: current.ability,
      currentFocus: current.focus,
      coveredTopics: coveredTopics.slice(0, 8),
      pendingTopics: pendingTopics.slice(0, 8),
    };
  }, [jobDescription, jobTitle, keywords, messages, streamingContent]);

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
          body: JSON.stringify({ interview_type: interviewType }),
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
  }, [addMessage, addToast, authHeaders, clearMessages, interviewType, keywords.length, navigate, setSessionId]);

  // ===== 自动滚动到底部 =====
  useEffect(() => {
    const container = chatContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, [messages, streamingContent]);

  // ===== 监听滚动位置，显示/隐藏"滚动到底部"按钮 =====
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      setShowScrollToBottom(scrollHeight - scrollTop - clientHeight > 150);
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

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

  const scrollToBottom = useCallback(() => {
    const container = chatContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, []);

  // ===== 停止生成 =====
  const handleStopGeneration = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    // 保存已生成的部分内容
    if (streamingContent.trim()) {
      addMessage({ role: "assistant", content: streamingContent });
    }
    setStreamingContent("");
    setStatusText("");
    setStreaming(false);
  }, [streamingContent, addMessage, setStreaming]);

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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaResize = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInputValue(e.target.value);
      const target = e.target;
      target.style.height = "auto";
      target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
    },
    []
  );

  // 自定义拖拽 resize 句柄（右上角，参考 Gemini 风格）
  const handleResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isResizingRef.current = true;
    startDragYRef.current = e.clientY;
    const textarea = inputRef.current;
    if (textarea) {
      startHeightRef.current = textarea.offsetHeight;
    }

    document.body.style.userSelect = "none";
    document.body.style.cursor = "ns-resize";

    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizingRef.current) return;
      const delta = startDragYRef.current - ev.clientY;
      const newHeight = Math.max(52, Math.min(400, startHeightRef.current + delta));
      if (textarea) {
        textarea.style.height = `${newHeight}px`;
      }
    };

    const onMouseUp = () => {
      isResizingRef.current = false;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, []);

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
        <div className="max-w-7xl mx-auto flex items-center justify-between">
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
                {(jobTitle || jobDescription) && (
                  <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
                    <BriefcaseBusiness className="h-3 w-3" />
                    {jobTitle || "已匹配岗位要求"}
                  </span>
                )}
                {keywords.map((kw) => (
                  <span
                    key={kw}
                    className="text-xs px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300"
                  >
                    {kw}
                  </span>
                ))}
                <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300">
                  {INTERVIEW_TYPE_LABELS[interviewType]}
                </span>
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

      <div className="min-h-0 flex-1 overflow-hidden px-4">
        <div className="max-w-7xl mx-auto grid h-full gap-0 lg:grid-cols-[minmax(0,1fr)_320px]">
          {/* 聊天区域 */}
          <div
            ref={chatContainerRef}
            className="min-h-0 overflow-y-auto py-6 lg:pr-5 scrollbar-thin relative"
          >
            <div className="mx-auto w-full max-w-5xl space-y-4">
              <div className="lg:hidden">
                <InterviewProgressPanel progress={interviewProgress} compact />
              </div>

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

            {/* 滚动到底部浮动按钮 */}
            {showScrollToBottom && (
              <button
                onClick={scrollToBottom}
                className="absolute bottom-4 left-1/2 -translate-x-1/2 w-9 h-9 rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700 transition-all flex items-center justify-center animate-fade-in z-10"
                title="滚动到底部"
              >
                <ArrowDown className="h-4 w-4" />
              </button>
            )}
          </div>

          <aside className="hidden min-h-0 border-l border-slate-200 dark:border-slate-800 py-6 lg:flex lg:justify-center">
            <div className="sticky top-6 w-full max-w-[270px]">
              <InterviewProgressPanel progress={interviewProgress} />
            </div>
          </aside>
        </div>
      </div>

      {/* 底部输入栏 */}
      <div className="shrink-0 border-t border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-gray-950/90 backdrop-blur-sm px-4 py-4">
        <div className="max-w-7xl mx-auto grid gap-0 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="mx-auto w-full max-w-5xl lg:pr-5">
            {statusText && isStreaming && (
              <div className="mb-2 flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400 animate-fade-in">
                <Loader2 className="h-3 w-3 animate-spin" />
                {statusText}
              </div>
            )}

            <div className="flex items-end gap-2">
              <div ref={textareaWrapperRef} className="flex-1 relative">
                {/* 自定义拖拽句柄 — 右上角（Gemini 风格） */}
                <div
                  className="absolute top-0 right-3 z-10 flex flex-col items-center gap-[2px] py-[6px] cursor-ns-resize opacity-30 hover:opacity-100 transition-opacity group"
                  onMouseDown={handleResizeMouseDown}
                  title="拖拽调整输入框高度"
                  role="separator"
                  aria-orientation="horizontal"
                  aria-label="拖拽调整输入区域高度"
                >
                  <span className="block w-6 h-[2px] rounded-full bg-slate-400 dark:bg-slate-500 group-hover:bg-blue-500 dark:group-hover:bg-blue-400 transition-colors" />
                  <span className="block w-4 h-[2px] rounded-full bg-slate-400 dark:bg-slate-500 group-hover:bg-blue-500 dark:group-hover:bg-blue-400 transition-colors" />
                </div>
                <textarea
                  ref={inputRef}
                  value={inputValue}
                  onChange={handleTextareaResize}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    isStreaming
                      ? "AI 正在回复中..."
                      : !sessionId
                      ? "正在连接面试官..."
                      : "输入你的回答... (Enter 发送, Shift+Enter 换行)"
                  }
                  disabled={isStreaming || !sessionId}
                  className={cn(
                    "w-full resize-none rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 px-4 py-3 pr-12 text-sm",
                    "min-h-[52px]",
                    "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder:text-slate-400 dark:placeholder:text-slate-600",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                    "transition-[height] duration-150 ease-out"
                  )}
                />
              </div>

              {isStreaming ? (
                <Button
                  onClick={handleStopGeneration}
                  variant="destructive"
                  size="icon"
                  className="shrink-0"
                  title="停止生成"
                >
                  <StopCircle className="h-5 w-5" />
                </Button>
              ) : (
                <Button
                  onClick={handleSend}
                  disabled={!inputValue.trim() || !sessionId}
                  size="icon"
                  className="shrink-0"
                >
                  <Send className="h-5 w-5" />
                </Button>
              )}
            </div>
          </div>
          <div className="hidden lg:block" />
        </div>
      </div>
    </div>
  );
}

function InterviewProgressPanel({
  progress,
  compact = false,
}: {
  progress: InterviewProgress;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 shadow-sm",
        compact ? "p-4" : "p-4"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <ClipboardList className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            考察进度
          </div>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            第 {progress.userTurnCount} / {MAX_INTERVIEW_TURNS} 轮
          </p>
        </div>
        <span className="rounded-full bg-blue-100 dark:bg-blue-900/40 px-2 py-1 text-xs font-semibold text-blue-700 dark:text-blue-300">
          {progress.percent}%
        </span>
      </div>

      <div className="mt-3 h-1.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-500"
          style={{ width: `${progress.percent}%` }}
        />
      </div>

      <div className="mt-4 rounded-lg border border-blue-200 dark:border-blue-900/60 bg-blue-50/70 dark:bg-blue-950/20 px-3 py-3">
        <div className="flex items-center gap-2 text-xs text-blue-700 dark:text-blue-300">
          <Gauge className="h-3.5 w-3.5" />
          当前能力
        </div>
        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
          {progress.currentAbility}
        </div>
        <div className="mt-0.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          {progress.currentFocus}
        </div>
      </div>

      <div className={cn("mt-4 grid gap-3", compact && "sm:grid-cols-2")}>
        <div>
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5" />
            已考察
          </div>
          <div className="flex flex-wrap gap-1.5 min-h-7">
            {progress.coveredTopics.length > 0 ? (
              progress.coveredTopics.map((topic) => (
                <span
                  key={topic}
                  className="rounded bg-emerald-100 dark:bg-emerald-900/40 px-2 py-1 text-xs text-emerald-700 dark:text-emerald-300"
                >
                  {topic}
                </span>
              ))
            ) : (
              <span className="text-xs text-slate-400 dark:text-slate-500">等待候选人开始回答</span>
            )}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
            <CircleDashed className="h-3.5 w-3.5" />
            待考察
          </div>
          <div className="flex flex-wrap gap-1.5 min-h-7">
            {progress.pendingTopics.map((topic) => (
              <span
                key={topic}
                className="rounded bg-slate-200 dark:bg-slate-800 px-2 py-1 text-xs text-slate-600 dark:text-slate-300"
              >
                {topic}
              </span>
            ))}
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
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

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
          "max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed relative group",
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

        {/* 复制按钮 */}
        {!isUser && !isStreaming && (
          <button
            onClick={handleCopy}
            className={cn(
              "absolute top-2 right-2 p-1.5 rounded-lg transition-all",
              "opacity-0 group-hover:opacity-100",
              "bg-white/80 dark:bg-slate-700/80 hover:bg-white dark:hover:bg-slate-600",
              "text-slate-400 hover:text-slate-600 dark:hover:text-slate-300",
              copied && "opacity-100 text-green-500"
            )}
            title="复制消息"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
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
