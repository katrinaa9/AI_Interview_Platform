import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft, TrendingUp, AlertTriangle, Lightbulb, Loader2,
  Clock, FileText, ChevronRight, History, Award,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { RadarChart } from "@/components/chart/RadarChart";
import { useAppStore } from "@/store";
import type { EvaluationReport, ReportHistoryItem } from "@/types";
import { cn } from "@/lib/utils";

export default function Report() {
  const navigate = useNavigate();
  const { token, sessionId, session } = useAppStore();

  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeSessionId, setActiveSessionId] = useState<string>(sessionId || "");

  const [history, setHistory] = useState<ReportHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const authHeaders = useCallback((): Record<string, string> => {
    const h: Record<string, string> = {};
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    setHistoryLoading(true);
    fetch("/api/report/history/list", { headers: authHeaders() })
      .then(res => res.ok ? res.json() : { items: [] })
      .then(data => {
        if (!cancelled) {
          const items: ReportHistoryItem[] = data.items || [];
          setHistory(items);
          if (!activeSessionId && items.length > 0) {
            setActiveSessionId(items[0].session_id);
          }
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setHistoryLoading(false); });
    return () => { cancelled = true; };
  }, [authHeaders]);

  useEffect(() => {
    if (!activeSessionId) {
      if (!historyLoading) {
        setLoading(false);
      }
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    const fetchReport = async () => {
      try {
        const res = await fetch(`/api/report/${activeSessionId}`, { headers: authHeaders() });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `服务器错误 (${res.status})`);
        }
        const data: EvaluationReport = await res.json();
        if (!cancelled) setReport(data);
      } catch (err: any) {
        if (!cancelled) setError(err.message || "网络异常，请稍后重试");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchReport();
    return () => { cancelled = true; };
  }, [activeSessionId, authHeaders]);

  const scoreValues = Object.values(report?.radar_scores ?? {}).filter(
    (v) => typeof v === "number"
  );
  const averageScore = scoreValues.length
    ? Math.round(scoreValues.reduce((a, b) => a + b, 0) / scoreValues.length)
    : 0;

  const durationText = report?.interview_duration || (() => {
    if (!session?.started_at) return "--";
    const start = new Date(session.started_at);
    const end = session.ended_at ? new Date(session.ended_at) : new Date();
    const mins = Math.max(1, Math.round((end.getTime() - start.getTime()) / 60000));
    return `${mins} 分钟`;
  })();

  const dateText = report?.interview_date
    ? new Date(report.interview_date).toLocaleDateString("zh-CN", {
        year: "numeric", month: "long", day: "numeric",
      })
    : session?.started_at
      ? new Date(session.started_at).toLocaleDateString("zh-CN", {
          year: "numeric", month: "long", day: "numeric",
        })
      : "--";

  const typeText = report?.interview_type || (
    session?.interview_type
      ? { technical: "基础技术面", pressure: "压力面试", friendly: "轻松聊天" }[session.interview_type] || session.interview_type
      : "--"
  );

  const handleSelectHistory = (sid: string) => {
    setActiveSessionId(sid);
  };

  if (loading && activeSessionId) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-20 text-center animate-fade-in">
        <Loader2 className="h-10 w-10 animate-spin mx-auto mb-4 text-blue-600" />
        <p className="text-slate-600 dark:text-slate-400 text-lg">
          {historyLoading ? "正在加载面试记录..." : "AI 正在分析面试表现，生成评估报告..."}
        </p>
      </div>
    );
  }

  if (!activeSessionId && !historyLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-12 animate-fade-in">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold">面试评估报告</h1>
          <Button onClick={() => navigate("/upload")}>开始新面试</Button>
        </div>
        {history.length > 0 ? (
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              你有 {history.length} 次历史面试记录，点击左侧查看报告
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {history.map((item) => {
                const dateStr = item.started_at
                  ? new Date(item.started_at).toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
                  : "--";
                return (
                  <button
                    key={item.session_id}
                    onClick={() => setActiveSessionId(item.session_id)}
                    className="text-left p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 hover:border-blue-400 dark:hover:border-blue-600 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-sm">{item.type_label}</span>
                      <ChevronRight className="h-4 w-4 text-slate-300" />
                    </div>
                    <div className="text-xs text-slate-500 mb-1">{dateStr} · {item.duration}</div>
                    {item.average_score !== null && (
                      <div className="flex items-center gap-1.5">
                        <Award className="h-3 w-3 text-amber-500" />
                        <span className={cn(
                          "text-xs font-semibold",
                          item.average_score >= 80 ? "text-green-600" :
                          item.average_score >= 60 ? "text-blue-600" :
                          item.average_score >= 40 ? "text-amber-600" : "text-red-600"
                        )}>
                          {item.average_score}分
                        </span>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="text-center py-16">
            <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
            <p className="text-slate-500 dark:text-slate-400 mb-2">暂无面试记录</p>
            <p className="text-sm text-slate-400 dark:text-slate-500 mb-6">
              完成一次面试后，评估报告将显示在这里
            </p>
            <Button onClick={() => navigate("/upload")}>去上传简历并开始面试</Button>
          </div>
        )}
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-lg mx-auto px-4 py-20 text-center animate-fade-in">
        <div className="p-8 rounded-2xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30">
          <AlertTriangle className="h-10 w-10 mx-auto mb-4 text-red-500" />
          <p className="text-red-700 dark:text-red-400 mb-2 font-medium">报告加载失败</p>
          <p className="text-sm text-red-600/70 dark:text-red-400/70 mb-6">{error}</p>
          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={() => navigate("/upload")}>返回首页</Button>
            <Button onClick={() => { setLoading(true); setError(""); setActiveSessionId(activeSessionId); }}>重试</Button>
          </div>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-20 text-center animate-fade-in">
        <p className="text-slate-500 dark:text-slate-400 mb-4">暂无评估数据</p>
        <Button onClick={() => navigate("/upload")}>返回首页</Button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate("/upload")} className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-3xl font-bold">面试评估报告</h1>
          <span className={cn(
            "px-3 py-1 rounded-full text-sm font-semibold",
            averageScore >= 80 ? "bg-gradient-to-r from-emerald-500 to-green-500 text-white" :
            averageScore >= 60 ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white" :
            averageScore >= 40 ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white" :
            "bg-gradient-to-r from-red-500 to-rose-500 text-white"
          )}>
            {averageScore >= 80 ? "优秀" : averageScore >= 60 ? "良好" : averageScore >= 40 ? "一般" : "需提升"}
          </span>
        </div>
        <div className="flex gap-2">
          {history.length > 0 && (
            <Button variant="outline" size="sm" onClick={() => setSidebarOpen(!sidebarOpen)}>
              <History className="h-4 w-4 mr-1" />
              {sidebarOpen ? "隐藏历史" : "查看历史"}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            <FileText className="h-4 w-4 mr-1" />
            打印
          </Button>
          <Button variant="outline" onClick={() => navigate("/upload")}>重新面试</Button>
        </div>
      </div>

      <div className="flex gap-6">
        {sidebarOpen && history.length > 0 && (
          <div className="w-64 flex-shrink-0">
            <div className="sticky top-24 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 overflow-hidden shadow-sm">
              <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-gradient-to-r from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-850">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <History className="h-4 w-4 text-blue-600" />
                  历史面试 ({history.length})
                </h3>
              </div>
              <div className="max-h-[600px] overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800">
                {historyLoading ? (
                  <div className="p-4 text-center"><Loader2 className="h-4 w-4 animate-spin mx-auto text-slate-400" /></div>
                ) : history.map((item) => {
                  const isActive = item.session_id === activeSessionId;
                  const dateStr = item.started_at
                    ? new Date(item.started_at).toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
                    : "--";
                  return (
                    <button
                      key={item.session_id}
                      onClick={() => handleSelectHistory(item.session_id)}
                      className={cn(
                        "w-full text-left px-4 py-3 transition-all hover:bg-slate-50 dark:hover:bg-slate-800/50",
                        isActive && "bg-blue-50 dark:bg-blue-950/30 border-l-2 border-l-blue-500"
                      )}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium truncate">{item.type_label}</span>
                        <ChevronRight className={cn("h-3.5 w-3.5 flex-shrink-0 transition-transform", isActive ? "text-blue-500" : "text-slate-300")} />
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span>{dateStr}</span>
                        <span>·</span>
                        <span>{item.duration}</span>
                      </div>
                      {item.average_score !== null && (
                        <div className="mt-1.5 flex items-center gap-1.5">
                          <Award className="h-3 w-3 text-amber-500" />
                          <span className={cn(
                            "text-xs font-semibold",
                            item.average_score >= 80 ? "text-green-600" :
                            item.average_score >= 60 ? "text-blue-600" :
                            item.average_score >= 40 ? "text-amber-600" : "text-red-600"
                          )}>
                            {item.average_score}分
                          </span>
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            {[
              { label: "面试日期", value: dateText, icon: Clock, gradient: "from-blue-500/10 to-indigo-500/10" },
              { label: "面试时长", value: durationText, icon: Clock, gradient: "from-purple-500/10 to-pink-500/10" },
              { label: "面试类型", value: typeText, icon: FileText, gradient: "from-amber-500/10 to-orange-500/10" },
              { label: "综合评分", value: `${averageScore} / 100`, icon: Award, gradient: "from-emerald-500/10 to-teal-500/10" },
            ].map((item) => (
              <div key={item.label} className={cn(
                "p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br",
                item.gradient,
                "backdrop-blur-sm shadow-sm hover:shadow-md transition-shadow"
              )}>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">{item.label}</p>
                  <item.icon className="h-4 w-4 text-slate-400 dark:text-slate-500" />
                </div>
                <p className="text-xl font-bold">{item.value}</p>
              </div>
            ))}
          </div>

          <div className="grid lg:grid-cols-5 gap-8">
            <div className="lg:col-span-2 space-y-4">
              <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 shadow-sm">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-blue-600" />
                  六维能力模型
                </h2>
                <RadarChart data={report.radar_scores} />
              </div>

              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 shadow-sm">
                <h3 className="text-sm font-semibold mb-3 text-slate-700 dark:text-slate-300">能力维度详情</h3>
                <div className="space-y-2">
                  {Object.entries(report.radar_scores).filter(([, v]) => typeof v === "number").map(([name, score]) => {
                    const scoreNum = score as number;
                    const barColor = scoreNum >= 80 ? "bg-emerald-500" : scoreNum >= 60 ? "bg-blue-500" : scoreNum >= 40 ? "bg-amber-500" : "bg-red-500";
                    return (
                      <div key={name} className="flex items-center gap-3">
                        <span className="text-xs text-slate-600 dark:text-slate-400 w-24 flex-shrink-0 truncate">{name}</span>
                        <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div className={cn("h-full rounded-full transition-all duration-500", barColor)} style={{ width: `${scoreNum}%` }} />
                        </div>
                        <span className={cn(
                          "text-xs font-semibold w-8 text-right",
                          scoreNum >= 80 ? "text-emerald-600" : scoreNum >= 60 ? "text-blue-600" : scoreNum >= 40 ? "text-amber-600" : "text-red-600"
                        )}>
                          {scoreNum}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="lg:col-span-3 space-y-4">
              {report.ai_feedback.总体评价 && (
                <div className="p-6 rounded-2xl border border-blue-200 dark:border-blue-900/50 bg-gradient-to-br from-blue-50 to-indigo-50/50 dark:from-blue-950/30 dark:to-indigo-950/20 shadow-sm">
                  <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-blue-700 dark:text-blue-400">
                    <TrendingUp className="h-5 w-5" />
                    总体评价
                  </h2>
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{report.ai_feedback.总体评价}</p>
                </div>
              )}

              <div className="p-6 rounded-2xl border border-green-200 dark:border-green-900/50 bg-gradient-to-br from-green-50 to-emerald-50/50 dark:from-green-950/30 dark:to-emerald-950/20 shadow-sm">
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-green-700 dark:text-green-400">
                  <Lightbulb className="h-5 w-5" />
                  核心优势
                </h2>
                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line">{report.ai_feedback.核心优势}</p>
              </div>

              <div className="p-6 rounded-2xl border border-amber-200 dark:border-amber-900/50 bg-gradient-to-br from-amber-50 to-orange-50/50 dark:from-amber-950/30 dark:to-orange-950/20 shadow-sm">
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="h-5 w-5" />
                  薄弱环节
                </h2>
                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line">{report.ai_feedback.薄弱环节}</p>
              </div>

              {report.ai_feedback.详细分析 && (
                <div className="p-6 rounded-2xl border border-purple-200 dark:border-purple-900/50 bg-gradient-to-br from-purple-50 to-pink-50/50 dark:from-purple-950/30 dark:to-pink-950/20 shadow-sm">
                  <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-purple-700 dark:text-purple-400">
                    <AlertTriangle className="h-5 w-5" />
                    六维详细分析
                  </h2>
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line">{report.ai_feedback.详细分析}</p>
                </div>
              )}

              <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 shadow-sm">
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-blue-600 dark:text-blue-400">
                  <TrendingUp className="h-5 w-5" />
                  改进建议
                </h2>
                <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line">
                  {report.ai_feedback.改进建议}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
