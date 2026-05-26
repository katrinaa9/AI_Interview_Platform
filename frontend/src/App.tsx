import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Navbar } from "@/components/layout/Navbar";
import Home from "@/pages/Home";
import Upload from "@/pages/Upload";
import Interview from "@/pages/Interview";
import Report from "@/pages/Report";
import Admin from "@/pages/Admin";
import Login from "@/pages/Login";
import { useAppStore } from "@/store";

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
    <BrowserRouter>
      <div className="min-h-screen bg-white dark:bg-gray-950 text-slate-900 dark:text-slate-100 transition-colors">
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/interview" element={<Interview />} />
            <Route path="/report" element={<Report />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<Home />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}