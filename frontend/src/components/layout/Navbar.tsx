import { Link, useLocation } from "react-router-dom";
import { Brain, FileUp, MessageSquare, BarChart3, LogIn, Settings } from "lucide-react";
import { useAppStore } from "@/store";
import { ThemeToggle } from "./ThemeToggle";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "首页", icon: Brain },
  { to: "/upload", label: "上传简历", icon: FileUp },
  { to: "/interview", label: "面试间", icon: MessageSquare },
  { to: "/report", label: "评估报告", icon: BarChart3 },
];

export function Navbar() {
  const location = useLocation();
  const { user, logout } = useAppStore();

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-gray-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <Brain className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">
              Ace<span className="text-blue-600">Interviewer</span>
            </span>
          </Link>

          {/* Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  location.pathname === to
                    ? "bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            ))}
            {user?.role === "admin" && (
              <Link
                to="/admin"
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  location.pathname === "/admin"
                    ? "bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                )}
              >
                <Settings className="h-4 w-4" />
                管理后台
              </Link>
            )}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {user ? (
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  {user.username}
                </span>
                <Button variant="outline" size="sm" onClick={logout}>
                  退出
                </Button>
              </div>
            ) : (
              <Link to="/login">
                <Button size="sm" className="gap-2">
                  <LogIn className="h-4 w-4" />
                  登录
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}