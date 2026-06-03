import { useEffect } from "react";
import { BrowserRouter, Navigate, Outlet, Routes, Route, useLocation } from "react-router-dom";
import { Navbar } from "@/components/layout/Navbar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import Home from "@/pages/Home";
import Upload from "@/pages/Upload";
import Interview from "@/pages/Interview";
import Report from "@/pages/Report";
import Admin from "@/pages/Admin";
import Login from "@/pages/Login";
import { useAppStore } from "@/store";

function RequireAuth() {
  const location = useLocation();
  const { token, user } = useAppStore();

  if (!token || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export default function App() {
  const { theme } = useAppStore();

  // 同步主题至 <html> 标签
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className="min-h-screen bg-white dark:bg-gray-950 text-slate-900 dark:text-slate-100 transition-colors">
          <Navbar />
          <main>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route element={<RequireAuth />}>
                <Route path="/" element={<Home />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/interview" element={<Interview />} />
                <Route path="/report" element={<Report />} />
                <Route path="/admin" element={<Admin />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
