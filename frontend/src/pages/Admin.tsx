import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus, Search, Trash2, Edit3, Loader2, AlertTriangle,
  ShieldAlert, ChevronLeft, ChevronRight, X, BarChart3,
  BookOpen, RefreshCw, Save, LayoutDashboard,
  FileText, Upload, Brain, ScrollText, Clock, Users,
  Database, Eye, RotateCcw, Copy, Check, UploadCloud,
  File, Activity, UserCog, UserCheck, UserX, BadgeCheck,
  MessageSquare, ShieldCheck, Ban, Award, Target, PieChart,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/store";
import { cn } from "@/lib/utils";

type TabKey = "dashboard" | "users" | "interviews" | "questions" | "documents" | "prompt" | "logs";

interface QuestionItem {
  id: string;
  category: string;
  question_text: string;
  reference_answer: string;
  difficulty: string;
  times_asked: number;
  times_wrong: number;
  created_at: string;
}

interface DocumentItem {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: string;
  chunk_count: number;
  error_message?: string;
  uploaded_by?: string;
  created_at: string;
  updated_at: string;
}

interface ChunkItem {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  category?: string;
  difficulty?: string;
  keywords?: string;
  created_at: string;
}

interface PromptVersion {
  id: string;
  version_number: number;
  content: string;
  description?: string;
  is_active: boolean;
  created_by?: string;
  created_at: string;
}

interface PromptTemplate {
  id: string;
  name: string;
  description?: string;
  content: string;
  is_builtin: boolean;
  created_by?: string;
  created_at: string;
}

interface AuditLogItem {
  id: string;
  operator: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  details?: string;
  status: string;
  ip_address?: string;
  created_at: string;
}

interface AdminUserItem {
  id: string;
  username: string;
  role: "student" | "admin";
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  interview_count: number;
  completed_interview_count: number;
  average_score: number | null;
  last_interview_at: string | null;
}

interface AdminInterviewItem {
  session_id: string;
  user_id: string;
  username: string;
  status: string;
  interview_type: string;
  type_label: string;
  started_at: string | null;
  ended_at: string | null;
  duration: string;
  average_score: number | null;
  has_report: boolean;
  message_count: number;
}

interface AdminInterviewReport {
  session: AdminInterviewItem;
  radar_scores?: Record<string, number>;
  ai_feedback?: Record<string, any>;
  created_at?: string;
}

interface DashboardStats {
  total_questions: number;
  total_documents: number;
  total_chunks: number;
  today_sessions: number;
  week_sessions: number;
  month_sessions: number;
  total_sessions: number;
  completed_sessions: number;
  average_score: number | null;
  interview_type_distribution: { type: string; label: string; count: number }[];
  weak_dimensions: { dimension: string; average_score: number; sample_count: number }[];
  failed_logs_count: number;
  total_users: number;
  recent_logs: AuditLogItem[];
}

const DIFFICULTY_LABELS: Record<string, string> = { easy: "简单", medium: "中等", hard: "困难" };
const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400",
  medium: "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400",
  hard: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400",
};
const STATUS_LABELS: Record<string, string> = {
  pending: "待处理", processing: "处理中", completed: "已完成", failed: "失败",
};
const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-400",
  processing: "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400",
  completed: "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400",
  failed: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400",
};
const ACTION_LABELS: Record<string, string> = {
  upload: "上传", batch_upload: "批量上传", delete: "删除", batch_delete: "批量删除",
  reprocess: "重新处理", create: "创建", update: "更新", save: "保存",
  rollback: "回滚", apply_template: "应用模板", role_update: "角色调整",
  status_update: "账号状态", delete_interview: "删除面试",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function Toast({ message, type, onClose }: { message: string; type: "success" | "error"; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div className={cn(
      "fixed top-20 right-4 z-[200] px-4 py-3 rounded-xl shadow-lg text-sm font-medium animate-fade-in flex items-center gap-2",
      type === "success"
        ? "bg-green-600 text-white"
        : "bg-red-600 text-white"
    )}>
      {type === "success" ? <Check className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
      {message}
    </div>
  );
}

export default function Admin() {
  const navigate = useNavigate();
  const { user, token } = useAppStore();
  const isAdmin = user?.role === "admin";

  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const authHeaders = useCallback((): Record<string, string> => {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
  }, [token]);

  const authHeadersNoCT = useCallback((): Record<string, string> => {
    const h: Record<string, string> = {};
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
  }, [token]);

  if (!isAdmin) {
    return (
      <div className="max-w-lg mx-auto px-4 py-20 text-center animate-fade-in">
        <div className="p-8 rounded-2xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30">
          <ShieldAlert className="h-12 w-12 mx-auto mb-4 text-red-500" />
          <h2 className="text-xl font-bold text-red-700 dark:text-red-400 mb-2">无访问权限</h2>
          <p className="text-sm text-red-600/70 dark:text-red-400/70 mb-6">此页面仅限管理员访问</p>
          <Button onClick={() => navigate("/")}>返回首页</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8 animate-fade-in">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">管理后台</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            AI 面试官核心控制台
          </p>
        </div>
      </div>

      <div className="flex gap-1 mb-6 p-1 rounded-xl bg-slate-100 dark:bg-slate-800 overflow-x-auto">
        {([
          { key: "dashboard", label: "仪表盘", icon: LayoutDashboard },
          { key: "users", label: "用户管理", icon: UserCog },
          { key: "interviews", label: "面试记录", icon: MessageSquare },
          { key: "questions", label: "题库管理", icon: BookOpen },
          { key: "documents", label: "知识库文档", icon: FileText },
          { key: "prompt", label: "提示词配置", icon: Brain },
          { key: "logs", label: "操作日志", icon: ScrollText },
        ] as { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap",
              activeTab === key
                ? "bg-white dark:bg-slate-700 shadow-sm"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {activeTab === "dashboard" && <DashboardTab authHeaders={authHeaders} />}
      {activeTab === "users" && <UsersTab authHeaders={authHeaders} setToast={setToast} />}
      {activeTab === "interviews" && <InterviewsTab authHeaders={authHeaders} setToast={setToast} />}
      {activeTab === "questions" && <QuestionsTab authHeaders={authHeaders} setToast={setToast} />}
      {activeTab === "documents" && <DocumentsTab authHeaders={authHeaders} authHeadersNoCT={authHeadersNoCT} setToast={setToast} />}
      {activeTab === "prompt" && <PromptTab authHeaders={authHeaders} setToast={setToast} />}
      {activeTab === "logs" && <LogsTab authHeaders={authHeaders} />}
    </div>
  );
}

function DashboardTab({ authHeaders }: { authHeaders: () => Record<string, string> }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const fetchingRef = useRef(false);

  const fetchStats = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    setLoading(true);
    try {
      const res = await fetch("/api/admin/dashboard/stats", { headers: authHeaders() });
      if (res.status === 429) {
        console.warn("Rate limit exceeded, skipping retry");
        return;
      }
      if (res.ok) setStats(await res.json());
    } catch { /* silent */ } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, [authHeaders]);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  if (loading) return <div className="py-12 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto text-blue-600" /></div>;
  if (!stats) return <div className="py-12 text-center text-slate-400">加载失败</div>;

  const cards = [
    { label: "题库总量", value: stats.total_questions, icon: BookOpen, color: "blue" },
    { label: "知识库文档", value: stats.total_documents, icon: FileText, color: "green" },
    { label: "知识片段", value: stats.total_chunks, icon: Database, color: "purple" },
    { label: "注册用户", value: stats.total_users, icon: Users, color: "indigo" },
    { label: "今日面试", value: stats.today_sessions, icon: Activity, color: "amber" },
    { label: "平均评分", value: stats.average_score ?? "--", icon: Award, color: "rose" },
  ];

  const colorMap: Record<string, string> = {
    blue: "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20",
    green: "border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20",
    purple: "border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/20",
    indigo: "border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-950/20",
    amber: "border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20",
    rose: "border-rose-200 dark:border-rose-800 bg-rose-50/50 dark:bg-rose-950/20",
  };
  const iconColorMap: Record<string, string> = {
    blue: "text-blue-600", green: "text-green-600", purple: "text-purple-600",
    indigo: "text-indigo-600", amber: "text-amber-600", rose: "text-rose-600",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">系统概览</h2>
        <Button variant="outline" size="sm" onClick={fetchStats}>
          <RefreshCw className="h-3.5 w-3.5 mr-1" />刷新
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className={cn("p-4 rounded-xl border", colorMap[color])}>
            <div className="flex items-center justify-between mb-2">
              <Icon className={cn("h-5 w-5", iconColorMap[color])} />
            </div>
            <div className="text-2xl font-bold">{value}</div>
            <div className="text-xs text-slate-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-gray-900">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="h-4 w-4 text-blue-600" />
            <h3 className="text-sm font-semibold">面试概览</h3>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="text-xl font-bold">{stats.total_sessions}</div>
              <div className="text-xs text-slate-500">总面试</div>
            </div>
            <div>
              <div className="text-xl font-bold">{stats.completed_sessions}</div>
              <div className="text-xs text-slate-500">已完成</div>
            </div>
            <div>
              <div className="text-xl font-bold">{stats.month_sessions}</div>
              <div className="text-xs text-slate-500">本月</div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-gray-900">
          <div className="flex items-center gap-2 mb-3">
            <PieChart className="h-4 w-4 text-emerald-600" />
            <h3 className="text-sm font-semibold">面试类型占比</h3>
          </div>
          {stats.interview_type_distribution.length === 0 ? (
            <div className="py-3 text-sm text-slate-400">暂无面试数据</div>
          ) : (
            <div className="space-y-2">
              {stats.interview_type_distribution.map((item) => {
                const percent = stats.total_sessions ? Math.round((item.count / stats.total_sessions) * 100) : 0;
                return (
                  <div key={item.type}>
                    <div className="flex justify-between text-xs mb-1">
                      <span>{item.label}</span>
                      <span className="text-slate-500">{item.count} 次 · {percent}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div className="h-full rounded-full bg-emerald-500" style={{ width: `${percent}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-gray-900">
          <div className="flex items-center gap-2 mb-3">
            <Target className="h-4 w-4 text-amber-600" />
            <h3 className="text-sm font-semibold">低分能力维度</h3>
          </div>
          {stats.weak_dimensions.length === 0 ? (
            <div className="py-3 text-sm text-slate-400">暂无评分数据</div>
          ) : (
            <div className="space-y-2">
              {stats.weak_dimensions.slice(0, 4).map((item) => (
                <div key={item.dimension} className="flex items-center justify-between text-sm">
                  <span className="truncate">{item.dimension}</span>
                  <span className={cn(
                    "font-semibold",
                    item.average_score >= 60 ? "text-blue-600" : item.average_score >= 40 ? "text-amber-600" : "text-red-600"
                  )}>
                    {item.average_score}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3 text-slate-700 dark:text-slate-300">最近操作日志</h3>
        {stats.recent_logs.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-sm">暂无操作日志</div>
        ) : (
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium">时间</th>
                  <th className="text-left px-4 py-2.5 font-medium">操作人</th>
                  <th className="text-left px-4 py-2.5 font-medium">操作</th>
                  <th className="text-left px-4 py-2.5 font-medium">资源</th>
                  <th className="text-left px-4 py-2.5 font-medium">详情</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {stats.recent_logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">{formatTime(log.created_at)}</td>
                    <td className="px-4 py-2.5">{log.operator}</td>
                    <td className="px-4 py-2.5">
                      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800">
                        {ACTION_LABELS[log.action] || log.action}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">{log.resource_type}</td>
                    <td className="px-4 py-2.5 text-slate-500 max-w-xs truncate">{log.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function UsersTab({
  authHeaders,
  setToast,
}: {
  authHeaders: () => Record<string, string>;
  setToast: (t: any) => void;
}) {
  const { user: currentUser } = useAppStore();
  const [users, setUsers] = useState<{ items: AdminUserItem[]; total: number; page: number; page_size: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [busyId, setBusyId] = useState("");

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "12" });
      if (search) params.set("search", search);
      if (roleFilter) params.set("role", roleFilter);
      if (statusFilter) params.set("is_active", statusFilter);
      const res = await fetch(`/api/admin/users?${params}`, { headers: authHeaders() });
      if (!res.ok) throw new Error("用户列表加载失败");
      setUsers(await res.json());
    } catch (e: any) {
      setToast({ message: e.message || "用户列表加载失败", type: "error" });
    } finally {
      setLoading(false);
    }
  }, [authHeaders, page, roleFilter, search, statusFilter, setToast]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const updateRole = async (target: AdminUserItem, role: "student" | "admin") => {
    if (target.role === role) return;
    setBusyId(target.id);
    try {
      const res = await fetch(`/api/admin/users/${target.id}/role`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({ role }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "角色更新失败");
      setToast({ message: "✅ 用户角色已更新", type: "success" });
      fetchUsers();
    } catch (e: any) {
      setToast({ message: e.message || "角色更新失败", type: "error" });
    } finally {
      setBusyId("");
    }
  };

  const updateStatus = async (target: AdminUserItem, isActive: boolean) => {
    if (target.is_active === isActive) return;
    const actionText = isActive ? "启用" : "禁用";
    if (!isActive && !window.confirm(`确定${actionText}用户「${target.username}」吗？`)) return;
    setBusyId(target.id);
    try {
      const res = await fetch(`/api/admin/users/${target.id}/status`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({ is_active: isActive }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || `${actionText}失败`);
      setToast({ message: `✅ 用户已${actionText}`, type: "success" });
      fetchUsers();
    } catch (e: any) {
      setToast({ message: e.message || `${actionText}失败`, type: "error" });
    } finally {
      setBusyId("");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[240px] flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { setSearch(searchInput.trim()); setPage(1); } }}
            placeholder="搜索用户名..."
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select value={roleFilter} onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
          className="h-10 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm">
          <option value="">全部角色</option>
          <option value="student">普通用户</option>
          <option value="admin">管理员</option>
        </select>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="h-10 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm">
          <option value="">全部状态</option>
          <option value="true">正常</option>
          <option value="false">已禁用</option>
        </select>
        <Button variant="outline" onClick={fetchUsers}><RefreshCw className="h-4 w-4 mr-1" />刷新</Button>
      </div>

      {loading ? (
        <div className="py-12 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto text-blue-600" /></div>
      ) : users && users.items.length === 0 ? (
        <div className="py-12 text-center text-slate-400">暂无用户数据</div>
      ) : users && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">用户</th>
                  <th className="text-left px-4 py-3 font-medium">角色</th>
                  <th className="text-left px-4 py-3 font-medium">状态</th>
                  <th className="text-center px-4 py-3 font-medium">面试</th>
                  <th className="text-center px-4 py-3 font-medium">均分</th>
                  <th className="text-left px-4 py-3 font-medium">最近面试</th>
                  <th className="text-right px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {users.items.map((item) => {
                  const isSelf = item.id === currentUser?.id;
                  return (
                    <tr key={item.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                      <td className="px-4 py-3">
                        <div className="font-medium">{item.username}</div>
                        <div className="text-xs text-slate-500">注册 {formatTime(item.created_at)}</div>
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={item.role}
                          disabled={busyId === item.id || isSelf}
                          onChange={(e) => updateRole(item, e.target.value as "student" | "admin")}
                          className="h-8 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 px-2 text-xs"
                        >
                          <option value="student">普通用户</option>
                          <option value="admin">管理员</option>
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium",
                          item.is_active
                            ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300"
                            : "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300"
                        )}>
                          {item.is_active ? <UserCheck className="h-3 w-3" /> : <UserX className="h-3 w-3" />}
                          {item.is_active ? "正常" : "已禁用"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="font-semibold">{item.interview_count}</div>
                        <div className="text-xs text-slate-500">完成 {item.completed_interview_count}</div>
                      </td>
                      <td className="px-4 py-3 text-center font-semibold">{item.average_score ?? "--"}</td>
                      <td className="px-4 py-3 text-slate-500">{item.last_interview_at ? formatTime(item.last_interview_at) : "--"}</td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busyId === item.id || isSelf}
                          onClick={() => updateStatus(item, !item.is_active)}
                        >
                          {busyId === item.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : item.is_active ? <Ban className="h-3.5 w-3.5 mr-1" /> : <ShieldCheck className="h-3.5 w-3.5 mr-1" />}
                          {item.is_active ? "禁用" : "启用"}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {users.total > users.page_size && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-800">
              <span className="text-sm text-slate-500">共 {users.total} 个用户</span>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="h-4 w-4" /></Button>
                <Button variant="outline" size="sm" disabled={page >= Math.ceil(users.total / users.page_size)} onClick={() => setPage(p => p + 1)}><ChevronRight className="h-4 w-4" /></Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InterviewsTab({
  authHeaders,
  setToast,
}: {
  authHeaders: () => Record<string, string>;
  setToast: (t: any) => void;
}) {
  const [interviews, setInterviews] = useState<{ items: AdminInterviewItem[]; total: number; page: number; page_size: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedReport, setSelectedReport] = useState<AdminInterviewReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AdminInterviewItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchInterviews = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "12" });
      if (search) params.set("search", search);
      if (statusFilter) params.set("status", statusFilter);
      if (typeFilter) params.set("interview_type", typeFilter);
      const res = await fetch(`/api/admin/interviews?${params}`, { headers: authHeaders() });
      if (!res.ok) throw new Error("面试记录加载失败");
      setInterviews(await res.json());
    } catch (e: any) {
      setToast({ message: e.message || "面试记录加载失败", type: "error" });
    } finally {
      setLoading(false);
    }
  }, [authHeaders, page, search, setToast, statusFilter, typeFilter]);

  useEffect(() => { fetchInterviews(); }, [fetchInterviews]);

  const viewReport = async (item: AdminInterviewItem) => {
    setLoadingReport(true);
    try {
      const res = await fetch(`/api/admin/interviews/${item.session_id}`, { headers: authHeaders() });
      if (!res.ok) throw new Error((await res.json()).detail || "报告加载失败");
      setSelectedReport(await res.json());
    } catch (e: any) {
      setToast({ message: e.message || "报告加载失败", type: "error" });
    } finally {
      setLoadingReport(false);
    }
  };

  const deleteInterview = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const res = await fetch(`/api/admin/interviews/${deleteTarget.session_id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "删除失败");
      setToast({ message: "✅ 面试记录已删除", type: "success" });
      setDeleteTarget(null);
      if (selectedReport?.session.session_id === deleteTarget.session_id) setSelectedReport(null);
      fetchInterviews();
    } catch (e: any) {
      setToast({ message: e.message || "删除失败", type: "error" });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[240px] flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { setSearch(searchInput.trim()); setPage(1); } }}
            placeholder="搜索用户名..."
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="h-10 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm">
          <option value="">全部状态</option>
          <option value="completed">已完成</option>
          <option value="ongoing">进行中</option>
        </select>
        <select value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="h-10 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm">
          <option value="">全部类型</option>
          <option value="technical">基础技术面</option>
          <option value="pressure">压力面试</option>
          <option value="friendly">轻松聊天</option>
        </select>
        <Button variant="outline" onClick={fetchInterviews}><RefreshCw className="h-4 w-4 mr-1" />刷新</Button>
      </div>

      {loading ? (
        <div className="py-12 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto text-blue-600" /></div>
      ) : interviews && interviews.items.length === 0 ? (
        <div className="py-12 text-center text-slate-400">暂无面试记录</div>
      ) : interviews && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">用户</th>
                  <th className="text-left px-4 py-3 font-medium">类型</th>
                  <th className="text-left px-4 py-3 font-medium">状态</th>
                  <th className="text-center px-4 py-3 font-medium">评分</th>
                  <th className="text-left px-4 py-3 font-medium">时长</th>
                  <th className="text-left px-4 py-3 font-medium">开始时间</th>
                  <th className="text-right px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {interviews.items.map((item) => (
                  <tr key={item.session_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-3">
                      <div className="font-medium">{item.username}</div>
                      <div className="text-xs text-slate-500">{item.message_count} 条对话</div>
                    </td>
                    <td className="px-4 py-3">{item.type_label}</td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        "rounded-full px-2 py-1 text-xs font-medium",
                        item.status === "completed"
                          ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300"
                          : "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300"
                      )}>
                        {item.status === "completed" ? "已完成" : "进行中"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center font-semibold">{item.average_score ?? "--"}</td>
                    <td className="px-4 py-3 text-slate-500">{item.duration}</td>
                    <td className="px-4 py-3 text-slate-500">{item.started_at ? formatTime(item.started_at) : "--"}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="outline" size="sm" onClick={() => viewReport(item)} disabled={loadingReport}>
                          <Eye className="h-3.5 w-3.5 mr-1" />报告
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setDeleteTarget(item)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {interviews.total > interviews.page_size && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-800">
              <span className="text-sm text-slate-500">共 {interviews.total} 条记录</span>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="h-4 w-4" /></Button>
                <Button variant="outline" size="sm" disabled={page >= Math.ceil(interviews.total / interviews.page_size)} onClick={() => setPage(p => p + 1)}><ChevronRight className="h-4 w-4" /></Button>
              </div>
            </div>
          )}
        </div>
      )}

      {selectedReport && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-3xl max-h-[86vh] overflow-y-auto bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-6">
            <div className="flex items-start justify-between gap-4 mb-5">
              <div>
                <h3 className="text-lg font-semibold">面试报告详情</h3>
                <p className="text-sm text-slate-500">
                  {selectedReport.session.username} · {selectedReport.session.type_label} · {selectedReport.session.duration}
                </p>
              </div>
              <button onClick={() => setSelectedReport(null)} className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
            </div>
            {selectedReport.radar_scores ? (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.entries(selectedReport.radar_scores).filter(([, score]) => typeof score === "number").map(([name, score]) => (
                    <div key={name}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{name}</span>
                        <span className="font-semibold">{score}</span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                        <div className="h-full rounded-full bg-blue-600" style={{ width: `${score}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
                {selectedReport.ai_feedback && (
                  <div className="space-y-3">
                    {["总体评价", "核心优势", "薄弱环节", "改进建议"].map((key) => (
                      selectedReport.ai_feedback?.[key] ? (
                        <div key={key} className="rounded-xl border border-slate-200 dark:border-slate-800 p-4">
                          <h4 className="text-sm font-semibold mb-2">{key}</h4>
                          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300 whitespace-pre-line">
                            {String(selectedReport.ai_feedback[key])}
                          </p>
                        </div>
                      ) : null
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="py-12 text-center text-slate-400">该面试暂无评估报告</div>
            )}
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-sm bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center"><Trash2 className="h-5 w-5 text-red-600" /></div>
              <div><h3 className="font-semibold">确认删除面试记录</h3><p className="text-sm text-slate-500">关联报告也会被删除</p></div>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
              {deleteTarget.username} · {deleteTarget.type_label} · {deleteTarget.started_at ? formatTime(deleteTarget.started_at) : "--"}
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setDeleteTarget(null)}>取消</Button>
              <Button variant="destructive" onClick={deleteInterview} disabled={deleting}>
                {deleting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                确认删除
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function QuestionsTab({ authHeaders, setToast }: { authHeaders: () => Record<string, string>; setToast: (t: any) => void }) {
  const [questions, setQuestions] = useState<{ items: QuestionItem[]; total: number; page: number; page_size: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({ category: "", question_text: "", reference_answer: "", difficulty: "medium" });
  const [submitting, setSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<QuestionItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const fetchingRef = useRef(false);

  const fetchQuestions = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "10" });
      if (categoryFilter) params.set("category", categoryFilter);
      if (search) params.set("search", search);
      const res = await fetch(`/api/admin/questions?${params}`, { headers: authHeaders() });
      if (res.status === 429) {
        console.warn("Rate limit exceeded on questions fetch");
        return;
      }
      if (res.ok) setQuestions(await res.json());
    } catch { /* silent */ } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, [page, search, categoryFilter, authHeaders]);

  useEffect(() => { fetchQuestions(); }, [fetchQuestions]);

  const handleSubmit = async () => {
    if (!formData.category.trim() || !formData.question_text.trim() || !formData.reference_answer.trim()) return;
    setSubmitting(true);
    try {
      const url = editingId ? `/api/admin/questions/${editingId}` : "/api/admin/questions";
      const method = editingId ? "PUT" : "POST";
      const res = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(formData) });
      if (!res.ok) throw new Error((await res.json()).detail || "操作失败");
      setShowForm(false);
      setToast({ message: editingId ? "✅ 题目已更新" : "✅ 题目已创建", type: "success" });
      fetchQuestions();
    } catch (e: any) { setToast({ message: e.message, type: "error" }); } finally { setSubmitting(false); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const res = await fetch(`/api/admin/questions/${deleteTarget.id}`, { method: "DELETE", headers: authHeaders() });
      if (!res.ok) throw new Error("删除失败");
      setDeleteTarget(null);
      setToast({ message: "✅ 题目已删除", type: "success" });
      fetchQuestions();
    } catch { setToast({ message: "删除失败", type: "error" }); } finally { setDeleting(false); }
  };

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-4 items-center">
        <div className="flex-1 min-w-[200px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { setSearch(searchInput.trim()); setPage(1); } }}
            placeholder="搜索题目..." className="w-full h-10 pl-10 pr-4 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <select value={categoryFilter} onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
          className="h-10 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">全部标签</option>
          {["React", "Vue", "TypeScript", "JavaScript", "Python", "Java", "MySQL", "Redis", "Docker"].map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <Button onClick={() => { setEditingId(null); setFormData({ category: "", question_text: "", reference_answer: "", difficulty: "medium" }); setShowForm(true); }}>
          <Plus className="h-4 w-4 mr-1" />新增题目
        </Button>
      </div>

      {loading ? (
        <div className="py-12 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto text-blue-600" /></div>
      ) : questions && questions.items.length === 0 ? (
        <div className="py-12 text-center text-slate-400">暂无题目数据</div>
      ) : questions && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">题目</th>
                  <th className="text-left px-4 py-3 font-medium w-24">标签</th>
                  <th className="text-left px-4 py-3 font-medium w-16">难度</th>
                  <th className="text-center px-4 py-3 font-medium w-16">抽取</th>
                  <th className="text-center px-4 py-3 font-medium w-16">错误</th>
                  <th className="text-right px-4 py-3 font-medium w-24">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {questions.items.map((q) => (
                  <tr key={q.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-3"><div className="max-w-md truncate">{q.question_text}</div></td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800">{q.category}</span></td>
                    <td className="px-4 py-3"><span className={cn("px-2 py-0.5 rounded text-xs font-medium", DIFFICULTY_COLORS[q.difficulty])}>{DIFFICULTY_LABELS[q.difficulty]}</span></td>
                    <td className="px-4 py-3 text-center text-slate-500">{q.times_asked}</td>
                    <td className="px-4 py-3 text-center text-slate-500">{q.times_wrong}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => { setEditingId(q.id); setFormData({ category: q.category, question_text: q.question_text, reference_answer: q.reference_answer, difficulty: q.difficulty }); setShowForm(true); }} className="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 hover:text-blue-600"><Edit3 className="h-4 w-4" /></button>
                        <button onClick={() => setDeleteTarget(q)} className="p-1.5 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 text-slate-500 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {questions.total > 10 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-800">
              <span className="text-sm text-slate-500">共 {questions.total} 条</span>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="h-4 w-4" /></Button>
                <Button variant="outline" size="sm" disabled={page >= Math.ceil(questions.total / 10)} onClick={() => setPage(p => p + 1)}><ChevronRight className="h-4 w-4" /></Button>
              </div>
            </div>
          )}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-lg bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-semibold">{editingId ? "编辑题目" : "新增题目"}</h3>
              <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">技术标签</label>
                <input type="text" value={formData.category} onChange={(e) => setFormData(f => ({ ...f, category: e.target.value }))} placeholder="如 React、Python" className="w-full h-10 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">题目内容</label>
                <textarea value={formData.question_text} onChange={(e) => setFormData(f => ({ ...f, question_text: e.target.value }))} rows={3} className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">参考答案</label>
                <textarea value={formData.reference_answer} onChange={(e) => setFormData(f => ({ ...f, reference_answer: e.target.value }))} rows={4} className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">难度</label>
                <select value={formData.difficulty} onChange={(e) => setFormData(f => ({ ...f, difficulty: e.target.value }))} className="w-full h-10 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="easy">简单</option><option value="medium">中等</option><option value="hard">困难</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <Button variant="outline" onClick={() => setShowForm(false)}>取消</Button>
              <Button onClick={handleSubmit} disabled={submitting}>{submitting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}{editingId ? "保存修改" : "创建题目"}</Button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-sm bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center"><Trash2 className="h-5 w-5 text-red-600" /></div>
              <div><h3 className="font-semibold">确认删除</h3><p className="text-sm text-slate-500">此操作不可撤销</p></div>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-1 line-clamp-2">{deleteTarget.question_text}</p>
            <div className="flex justify-end gap-3 mt-6">
              <Button variant="outline" onClick={() => setDeleteTarget(null)}>取消</Button>
              <Button variant="destructive" onClick={handleDelete} disabled={deleting}>{deleting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}确认删除</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DocumentsTab({ authHeaders, authHeadersNoCT, setToast }: { authHeaders: () => Record<string, string>; authHeadersNoCT: () => Record<string, string>; setToast: (t: any) => void }) {
  const [docs, setDocs] = useState<{ items: DocumentItem[]; total: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [deleteDocTarget, setDeleteDocTarget] = useState<DocumentItem | null>(null);
  const fetchingRef = useRef(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const docsRef = useRef<{ items: DocumentItem[]; total: number } | null>(null);

  const fetchDocs = useCallback(async (force = false) => {
    if (fetchingRef.current && !force) return;
    fetchingRef.current = true;
    if (!docsRef.current) setLoading(true);
    try {
      const res = await fetch("/api/admin/documents?page_size=50", { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        docsRef.current = data;
        setDocs(data);
      }
    } catch { /* silent */ } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, [authHeaders]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  useEffect(() => {
    if (!docs) return;
    const hasPending = docs.items.some(d => d.status === "pending" || d.status === "processing");
    if (hasPending) {
      pollTimerRef.current = setTimeout(() => fetchDocs(true), 3000);
    }
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [docs, fetchDocs]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const formData = new FormData();
      let newDocs: DocumentItem[] = [];

      if (files.length === 1) {
        formData.append("file", files[0]);
        const res = await fetch("/api/admin/documents/upload", { method: "POST", headers: authHeadersNoCT(), body: formData });
        if (!res.ok) {
          const errData = await res.json().catch(() => null);
          throw new Error(errData?.detail || "上传失败");
        }
        const doc: DocumentItem = await res.json();
        newDocs = [doc];
        setToast({ message: `✅ ${files[0].name} 已上传，正在后台处理`, type: "success" });
      } else {
        for (const f of files) formData.append("files", f);
        const res = await fetch("/api/admin/documents/upload/batch", { method: "POST", headers: authHeadersNoCT(), body: formData });
        if (!res.ok) {
          const errData = await res.json().catch(() => null);
          throw new Error(errData?.detail || "批量上传失败");
        }
        newDocs = await res.json();
        setToast({ message: `✅ ${files.length} 个文件已上传，正在后台处理`, type: "success" });
      }

      if (newDocs.length > 0) {
        setDocs(prev => {
          const existing = prev?.items || [];
          const existingIds = new Set(newDocs.map(d => d.id));
          const filtered = existing.filter(d => !existingIds.has(d.id));
          return { items: [...newDocs, ...filtered], total: (prev?.total || 0) + newDocs.length };
        });
      }

      setTimeout(() => fetchDocs(true), 1500);
    } catch (e: any) {
      setToast({ message: `❌ ${e.message}`, type: "error" });
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      const res = await fetch(`/api/admin/documents/${docId}`, { method: "DELETE", headers: authHeaders() });
      if (!res.ok) throw new Error("删除失败");
      setToast({ message: "✅ 文档已删除", type: "success" });
      setDeleteDocTarget(null);
      if (selectedDoc?.id === docId) { setSelectedDoc(null); setChunks([]); }
      setDocs(prev => prev ? {
        items: prev.items.filter(d => d.id !== docId),
        total: prev.total - 1,
      } : null);
    } catch { setToast({ message: "删除失败", type: "error" }); }
  };

  const handleReprocess = async (docId: string) => {
    try {
      const res = await fetch(`/api/admin/documents/reprocess/${docId}`, { method: "POST", headers: authHeaders() });
      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "处理失败");
      }
      setToast({ message: "✅ 已开始重新处理", type: "success" });
      fetchDocs(true);
    } catch (e: any) { setToast({ message: `❌ ${e.message}`, type: "error" }); }
  };

  const viewChunks = async (doc: DocumentItem) => {
    setSelectedDoc(doc);
    setLoadingChunks(true);
    setChunks([]); // 清空旧数据
    try {
      const res = await fetch(`/api/admin/documents/${doc.id}/chunks?page_size=100`, { headers: authHeaders() });
      if (!res.ok) {
        throw new Error(`获取知识片段失败 (${res.status})`);
      }
      const data = await res.json();
      setChunks(data.items || []);
      
      if (!data.items || data.items.length === 0) {
        setToast({ message: `⚠️ 该文档暂无知识片段`, type: "success" });
      }
    } catch (e: any) {
      setToast({ message: `❌ ${e.message}`, type: "error" });
      setChunks([]);
    } finally {
      setLoadingChunks(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">知识库文档管理</h2>
          <p className="text-sm text-slate-500">上传文档自动解析为知识片段，支持 PDF / TXT / MD 格式</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => fetchDocs()}><RefreshCw className="h-3.5 w-3.5 mr-1" />刷新</Button>
          <input ref={fileInputRef} type="file" accept=".pdf,.txt,.md" multiple className="hidden" onChange={(e) => { handleUpload(e.target.files); e.target.value = ""; }} />
          <Button size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Upload className="h-4 w-4 mr-1" />}
            上传文档
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto text-blue-600" /></div>
      ) : docs && docs.items.length === 0 ? (
        <div className="py-16 text-center">
          <UploadCloud className="h-12 w-12 mx-auto text-slate-300 dark:text-slate-600 mb-4" />
          <p className="text-slate-400">暂无文档，点击上方按钮上传</p>
        </div>
      ) : docs && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {docs.items.map((doc) => (
            <div key={doc.id} className={cn(
              "p-4 rounded-xl border transition-colors cursor-pointer",
              selectedDoc?.id === doc.id
                ? "border-blue-400 dark:border-blue-600 bg-blue-50/50 dark:bg-blue-950/20"
                : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
            )} onClick={() => viewChunks(doc)}>
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <File className="h-5 w-5 text-slate-400" />
                  <span className="font-medium text-sm truncate max-w-[200px]" title={doc.filename}>{doc.filename}</span>
                </div>
                <span className={cn("px-2 py-0.5 rounded text-xs font-medium", STATUS_COLORS[doc.status] || "")}>
                  {STATUS_LABELS[doc.status] || doc.status}
                </span>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-500 mb-3">
                <span>{formatSize(doc.file_size)}</span>
                <span>{doc.chunk_count} 片段</span>
                <span>{formatTime(doc.created_at)}</span>
              </div>
              {doc.error_message && (
                <p className="text-xs text-red-500 mb-2 truncate" title={doc.error_message}>{doc.error_message}</p>
              )}
              <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                <Button variant="outline" size="sm" onClick={() => viewChunks(doc)}><Eye className="h-3.5 w-3.5 mr-1" />查看片段</Button>
                <Button variant="outline" size="sm" onClick={() => handleReprocess(doc.id)}><RotateCcw className="h-3.5 w-3.5 mr-1" />重新处理</Button>
                <Button variant="outline" size="sm" onClick={() => setDeleteDocTarget(doc)}><Trash2 className="h-3.5 w-3.5" /></Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedDoc && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4">
          <h3 className="text-sm font-semibold mb-3">知识片段 — {selectedDoc.filename} ({chunks.length} 个)</h3>
          {loadingChunks ? (
            <div className="py-8 text-center"><Loader2 className="h-5 w-5 animate-spin mx-auto text-blue-600" /></div>
          ) : chunks.length === 0 ? (
            <div className="py-8 text-center text-slate-400 text-sm">暂无知识片段</div>
          ) : (
            <div className="space-y-3 max-h-[500px] overflow-y-auto">
              {chunks.map((chunk, i) => (
                <div key={chunk.id} className="p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-gray-900">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-400">片段 #{chunk.chunk_index + 1}</span>
                    <div className="flex gap-2">
                      {chunk.category && <span className="px-1.5 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800">{chunk.category}</span>}
                      {chunk.difficulty && <span className={cn("px-1.5 py-0.5 rounded text-xs", DIFFICULTY_COLORS[chunk.difficulty])}>{DIFFICULTY_LABELS[chunk.difficulty]}</span>}
                    </div>
                  </div>
                  <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap line-clamp-4">{chunk.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {deleteDocTarget && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-sm bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center"><Trash2 className="h-5 w-5 text-red-600" /></div>
              <div><h3 className="font-semibold">确认删除文档</h3><p className="text-sm text-slate-500">关联的知识片段也将被删除</p></div>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 truncate">{deleteDocTarget.filename}</p>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setDeleteDocTarget(null)}>取消</Button>
              <Button variant="destructive" onClick={() => handleDeleteDoc(deleteDocTarget.id)}>确认删除</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PromptTab({ authHeaders, setToast }: { authHeaders: () => Record<string, string>; setToast: (t: any) => void }) {
  const [content, setContent] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [showVersions, setShowVersions] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [hasCustom, setHasCustom] = useState(false);
  const fetchingActiveRef = useRef(false);
  const fetchingVersionsRef = useRef(false);
  const fetchingTemplatesRef = useRef(false);

  const fetchActive = useCallback(async () => {
    if (fetchingActiveRef.current) return;
    fetchingActiveRef.current = true;
    try {
      const res = await fetch("/api/admin/prompt/active", { headers: authHeaders() });
      if (res.status === 429) return;
      if (res.ok) {
        const data = await res.json();
        setContent(data.content || "");
        setHasCustom(data.has_custom);
      }
    } catch { /* silent */ } finally { fetchingActiveRef.current = false; }
  }, [authHeaders]);

  const fetchVersions = useCallback(async () => {
    if (fetchingVersionsRef.current) return;
    fetchingVersionsRef.current = true;
    try {
      const res = await fetch("/api/admin/prompt/versions", { headers: authHeaders() });
      if (res.status === 429) return;
      if (res.ok) { const data = await res.json(); setVersions(data.items); }
    } catch { /* silent */ } finally { fetchingVersionsRef.current = false; }
  }, [authHeaders]);

  const fetchTemplates = useCallback(async () => {
    if (fetchingTemplatesRef.current) return;
    fetchingTemplatesRef.current = true;
    try {
      const res = await fetch("/api/admin/prompt/templates", { headers: authHeaders() });
      if (res.status === 429) return;
      if (res.ok) setTemplates(await res.json());
    } catch { /* silent */ } finally { fetchingTemplatesRef.current = false; }
  }, [authHeaders]);

  useEffect(() => { fetchActive(); fetchVersions(); fetchTemplates(); }, [fetchActive, fetchVersions, fetchTemplates]);

  const handleSave = async () => {
    if (!content.trim()) return;
    setSaving(true);
    try {
      const res = await fetch("/api/admin/prompt/save", {
        method: "POST", headers: authHeaders(),
        body: JSON.stringify({ content, description: description || undefined }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "保存失败");
      setToast({ message: "✅ AI 面试官人设已更新", type: "success" });
      setDescription("");
      fetchVersions();
    } catch (e: any) { setToast({ message: e.message, type: "error" }); } finally { setSaving(false); }
  };

  const handleRollback = async (versionId: string) => {
    try {
      const res = await fetch(`/api/admin/prompt/rollback/${versionId}`, { method: "POST", headers: authHeaders() });
      if (!res.ok) throw new Error("回滚失败");
      setToast({ message: "✅ 已回滚到历史版本", type: "success" });
      fetchActive();
      fetchVersions();
    } catch { setToast({ message: "回滚失败", type: "error" }); }
  };

  const handleApplyTemplate = async (templateId: string) => {
    try {
      const res = await fetch(`/api/admin/prompt/templates/${templateId}/apply`, { method: "POST", headers: authHeaders() });
      if (!res.ok) throw new Error("应用失败");
      setToast({ message: "✅ 模板已应用", type: "success" });
      fetchActive();
      fetchVersions();
      setShowTemplates(false);
    } catch { setToast({ message: "应用模板失败", type: "error" }); }
  };

  const handlePreviewTemplate = (tpl: PromptTemplate) => {
    setContent(tpl.content);
    setShowTemplates(false);
    setToast({ message: `已加载模板「${tpl.name}」到编辑器，保存后生效`, type: "success" });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">AI 面试官系统提示词</h2>
          <p className="text-sm text-slate-500">
            {hasCustom ? "当前使用自定义提示词" : "当前使用默认提示词"}
            {content.length > 0 && ` · ${content.length} 字符`}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowTemplates(!showTemplates)}>
            <Copy className="h-3.5 w-3.5 mr-1" />模板库
          </Button>
          <Button variant="outline" size="sm" onClick={() => { setShowVersions(!showVersions); fetchVersions(); }}>
            <Clock className="h-3.5 w-3.5 mr-1" />版本历史
          </Button>
        </div>
      </div>

      {showTemplates && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4">
          <h3 className="text-sm font-semibold mb-3">提示词模板库</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {templates.map((tpl) => (
              <div key={tpl.id} className="p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-gray-900">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">{tpl.name}</span>
                  {tpl.is_builtin && <span className="px-1.5 py-0.5 rounded text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400">内置</span>}
                </div>
                <p className="text-xs text-slate-500 mb-3">{tpl.description}</p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => handlePreviewTemplate(tpl)}>加载到编辑器</Button>
                  <Button size="sm" onClick={() => handleApplyTemplate(tpl.id)}>直接应用</Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showVersions && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4">
          <h3 className="text-sm font-semibold mb-3">版本历史 ({versions.length})</h3>
          {versions.length === 0 ? (
            <p className="text-sm text-slate-400 py-4 text-center">暂无历史版本</p>
          ) : (
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {versions.map((v) => (
                <div key={v.id} className={cn(
                  "flex items-center justify-between p-3 rounded-lg border",
                  v.is_active ? "border-green-300 dark:border-green-700 bg-green-50/50 dark:bg-green-950/20" : "border-slate-200 dark:border-slate-700"
                )}>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">v{v.version_number}</span>
                      {v.is_active && <span className="px-1.5 py-0.5 rounded text-xs bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400">当前</span>}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{v.description} · {v.created_by} · {formatTime(v.created_at)}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => { setContent(v.content); setShowVersions(false); }}>查看</Button>
                    {!v.is_active && <Button size="sm" onClick={() => handleRollback(v.id)}>回滚</Button>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium">系统提示词编辑器</label>
          <span className={cn("text-xs", content.length > 8000 ? "text-amber-500" : "text-slate-400")}>
            {content.length} 字符 {content.length > 8000 && "(建议精简)"}
          </span>
        </div>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="w-full h-[450px] p-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 font-mono text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
          placeholder="输入 AI 面试官的系统提示词..."
          spellCheck={false}
        />
      </div>

      <div className="flex items-center gap-3">
        <input
          type="text" value={description} onChange={(e) => setDescription(e.target.value)}
          placeholder="版本说明（可选，如：优化了追问策略）"
          className="flex-1 h-10 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <Button onClick={handleSave} disabled={saving || !content.trim()}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
          保存并生效
        </Button>
      </div>
    </div>
  );
}

function LogsTab({ authHeaders }: { authHeaders: () => Record<string, string> }) {
  const [logs, setLogs] = useState<{ items: AuditLogItem[]; total: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");
  const fetchingRef = useRef(false);

  const fetchLogs = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "20" });
      if (actionFilter) params.set("action", actionFilter);
      if (resourceFilter) params.set("resource_type", resourceFilter);
      const res = await fetch(`/api/admin/audit/logs?${params}`, { headers: authHeaders() });
      if (res.status === 429) {
        console.warn("Rate limit exceeded on logs fetch");
        return;
      }
      if (res.ok) setLogs(await res.json());
    } catch { /* silent */ } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, [page, actionFilter, resourceFilter, authHeaders]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">操作日志</h2>
        <Button variant="outline" size="sm" onClick={fetchLogs}><RefreshCw className="h-3.5 w-3.5 mr-1" />刷新</Button>
      </div>

      <div className="flex gap-3">
        <select value={actionFilter} onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="h-9 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">全部操作</option>
          {Object.entries(ACTION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={resourceFilter} onChange={(e) => { setResourceFilter(e.target.value); setPage(1); }}
          className="h-9 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">全部资源</option>
          <option value="document">文档</option>
          <option value="chunk">知识片段</option>
          <option value="prompt_version">提示词版本</option>
          <option value="prompt_template">提示词模板</option>
          <option value="question">题目</option>
        </select>
      </div>

      {loading ? (
        <div className="py-12 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto text-blue-600" /></div>
      ) : logs && logs.items.length === 0 ? (
        <div className="py-12 text-center text-slate-400">暂无日志记录</div>
      ) : logs && (
        <>
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium w-32">时间</th>
                  <th className="text-left px-4 py-2.5 font-medium w-20">操作人</th>
                  <th className="text-left px-4 py-2.5 font-medium w-20">操作</th>
                  <th className="text-left px-4 py-2.5 font-medium w-24">资源类型</th>
                  <th className="text-left px-4 py-2.5 font-medium">详情</th>
                  <th className="text-center px-4 py-2.5 font-medium w-16">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {logs.items.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-2.5 text-slate-500 text-xs whitespace-nowrap">{formatTime(log.created_at)}</td>
                    <td className="px-4 py-2.5 text-xs">{log.operator}</td>
                    <td className="px-4 py-2.5">
                      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800">{ACTION_LABELS[log.action] || log.action}</span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">{log.resource_type}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-500 max-w-xs truncate">{log.details}</td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn("px-1.5 py-0.5 rounded text-xs", log.status === "success" ? "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400" : "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400")}>
                        {log.status === "success" ? "成功" : "失败"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {logs.total > 20 && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500">共 {logs.total} 条</span>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="h-4 w-4" /></Button>
                <Button variant="outline" size="sm" disabled={page >= Math.ceil(logs.total / 20)} onClick={() => setPage(p => p + 1)}><ChevronRight className="h-4 w-4" /></Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
