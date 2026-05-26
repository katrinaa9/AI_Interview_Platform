import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, TrendingUp, AlertTriangle, Lightbulb, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { RadarChart } from "@/components/chart/RadarChart";
import { useAppStore } from "@/store";
import type { EvaluationReport } from "@/types";

export default function Report() {
  const navigate = useNavigate();
  const { token, sessionId, session } = useAppStore();

  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ===== 从后端获取评估报告 =====
  useEffect(() => {
    if (!sessionId) {
      setError("未找到面试会话记录，请先完成一次面试");
      setLoading(false);
      return;
    }

    let cancelled = false;

    const fetchReport = async () => {
      try {
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`/api/report/${sessionId}`, { headers });

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

    return () => {
      cancelled = true;
    };
  }, [sessionId, token]);

  // ===== 计算衍生数据 =====
  const scoreValues = Object.values(report?.radar_scores ?? {}).filter(
    (v) => typeof v === "number"
  );
  const averageScore = scoreValues.length
    ? Math.round(scoreValues.reduce((a, b) => a + b, 0) / scoreValues.length)
    : 0;

  // 面试元数据：优先使用 API 返回的数据，其次从 store 推算
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

  // ===== 加载态 =====
  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-20 text-center animate-fade-in">
        <Loader2 className="h-10 w-10 animate-spin mx-auto mb-4 text-blue-600" />
        <p className="text-slate-600 dark:text-slate-400 text-lg">
          AI 正在分析你的面试表现，生成评估报告...
        </p>
        <p className="text-sm text-slate-400 dark:text-slate-500 mt-2">
          这可能需要几秒钟，请耐心等待
        </p>
      </div>
    );
  }

  // ===== 错误态：无会话 =====
  if (error && !sessionId) {
    return (
      <div className="max-w-lg mx-auto px-4 py-20 text-center animate-fade-in">
        <div className="p-8 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900">
          <AlertTriangle className="h-10 w-10 mx-auto mb-4 text-amber-500" />
          <p className="text-slate-700 dark:text-slate-300 mb-6">{error}</p>
          <Button onClick={() => navigate("/upload")}>去上传简历</Button>
        </div>
      </div>
    );
  }

  // ===== 错误态：API 失败 =====
  if (error) {
    return (
      <div className="max-w-lg mx-auto px-4 py-20 text-center animate-fade-in">
        <div className="p-8 rounded-2xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30">
          <AlertTriangle className="h-10 w-10 mx-auto mb-4 text-red-500" />
          <p className="text-red-700 dark:text-red-400 mb-2 font-medium">报告加载失败</p>
          <p className="text-sm text-red-600/70 dark:text-red-400/70 mb-6">{error}</p>
          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={() => navigate("/upload")}>
              返回首页
            </Button>
            <Button onClick={() => {
              setLoading(true);
              setError("");
              window.location.reload();
            }}>
              重试
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ===== 空数据防御 =====
  if (!report) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-20 text-center animate-fade-in">
        <p className="text-slate-500 dark:text-slate-400 mb-4">暂无评估数据</p>
        <Button onClick={() => navigate("/upload")}>返回首页</Button>
      </div>
    );
  }

  // ===== 正常渲染：真实数据 =====
  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:px-6 lg:px-8 animate-fade-in">
      {/* 顶部信息 */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/upload")}
            className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-3xl font-bold">面试评估报告</h1>
        </div>
        <Button variant="outline" onClick={() => navigate("/upload")}>
          重新面试
        </Button>
      </div>

      {/* 元数据卡片 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: "面试日期", value: dateText },
          { label: "面试时长", value: durationText },
          { label: "面试类型", value: typeText },
          { label: "综合评分", value: `${averageScore} / 100` },
        ].map((item) => (
          <div
            key={item.label}
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900"
          >
            <p className="text-xs text-slate-500 dark:text-slate-500 mb-1">
              {item.label}
            </p>
            <p className="text-lg font-bold">{item.value}</p>
          </div>
        ))}
      </div>

      {/* 主体：雷达图 + 文本反馈 */}
      <div className="grid lg:grid-cols-5 gap-8">
        {/* 左侧：雷达图 */}
        <div className="lg:col-span-2 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-600" />
            六维能力模型
          </h2>
          <RadarChart data={report.radar_scores} />
        </div>

        {/* 右侧：文本反馈 */}
        <div className="lg:col-span-3 space-y-4">
          {/* 总体评价 */}
          {report.ai_feedback.总体评价 && (
            <div className="p-6 rounded-2xl border border-blue-200 dark:border-blue-900/50 bg-blue-50/50 dark:bg-blue-950/20">
              <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-blue-700 dark:text-blue-400">
                <TrendingUp className="h-5 w-5" />
                总体评价
              </h2>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {report.ai_feedback.总体评价}
              </p>
            </div>
          )}

          {/* 核心优势 */}
          <div className="p-6 rounded-2xl border border-green-200 dark:border-green-900/50 bg-green-50/50 dark:bg-green-950/20">
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-green-700 dark:text-green-400">
              <Lightbulb className="h-5 w-5" />
              核心优势
            </h2>
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line">
              {report.ai_feedback.核心优势}
            </p>
          </div>

          {/* 薄弱环节 */}
          <div className="p-6 rounded-2xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-950/20">
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-5 w-5" />
              薄弱环节
            </h2>
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line">
              {report.ai_feedback.薄弱环节}
            </p>
          </div>

          {/* 详细分析（新增） */}
          {report.ai_feedback.详细分析 && (
            <div className="p-6 rounded-2xl border border-purple-200 dark:border-purple-900/50 bg-purple-50/50 dark:bg-purple-950/20">
              <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-purple-700 dark:text-purple-400">
                <AlertTriangle className="h-5 w-5" />
                六维详细分析
              </h2>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line">
                {report.ai_feedback.详细分析}
              </p>
            </div>
          )}

          {/* 改进建议 */}
          <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900">
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
  );
}