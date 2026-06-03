import { Link } from "react-router-dom";
import {
  Brain,
  FileUp,
  MessageSquare,
  BarChart3,
  Zap,
  TrendingUp,
  ChevronRight,
  User,
  Settings,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/store";

export default function Home() {
  const { user } = useAppStore();

  return (
    <div className="min-h-[calc(100vh-4rem)]">
      {user ? (
        /* ===== 已登录用户：快捷操作面板 ===== */
        <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-12 animate-fade-in">
          <div className="text-center mb-10">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center mx-auto mb-4">
              <User className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-3xl font-bold mb-2">
              你好，<span className="text-blue-600">{user.username}</span>
            </h1>
            <p className="text-slate-500 dark:text-slate-400">
              准备开始今天的模拟面试吗？
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <Link
              to="/upload"
              className="group p-6 rounded-2xl border border-blue-200 dark:border-blue-800 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/20 hover:shadow-lg hover:border-blue-300 dark:hover:border-blue-700 transition-all duration-300"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                    <FileUp className="h-5 w-5 text-white" />
                  </div>
                  <h3 className="text-lg font-semibold mb-1">开始新面试</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    上传简历，选择面试风格，开启 AI 模拟面试
                  </p>
                </div>
                <ChevronRight className="h-5 w-5 text-slate-300 group-hover:text-blue-500 transition-colors mt-1" />
              </div>
            </Link>

            <Link
              to="/report"
              className="group p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 hover:shadow-lg hover:border-blue-300 dark:hover:border-blue-700 transition-all duration-300"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                    <BarChart3 className="h-5 w-5 text-amber-600" />
                  </div>
                  <h3 className="text-lg font-semibold mb-1">查看历史报告</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    回顾过往面试评估，追踪能力成长轨迹
                  </p>
                </div>
                <ChevronRight className="h-5 w-5 text-slate-300 group-hover:text-blue-500 transition-colors mt-1" />
              </div>
            </Link>

            {user.role === "admin" && (
              <Link
                to="/admin"
                className="group p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 hover:shadow-lg hover:border-purple-300 dark:hover:border-purple-700 transition-all duration-300 sm:col-span-2"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                      <Settings className="h-5 w-5 text-purple-600" />
                    </div>
                    <h3 className="text-lg font-semibold mb-1">管理后台</h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      题库管理、用户管理、提示词配置等系统运维功能
                    </p>
                  </div>
                  <ChevronRight className="h-5 w-5 text-slate-300 group-hover:text-purple-500 transition-colors mt-1" />
                </div>
              </Link>
            )}
          </div>
        </section>
      ) : (
        /* ===== 未登录访客：营销落地页 ===== */
        <>
          <section className="relative overflow-hidden px-4 pt-20 pb-16 sm:px-6 lg:px-8">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-white to-indigo-50 dark:from-gray-950 dark:via-gray-950 dark:to-blue-950 -z-10" />
            <div className="max-w-4xl mx-auto text-center">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-sm font-medium mb-8">
                <Zap className="h-4 w-4" />
                基于 DeepSeek 大模型的智能面试引擎
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight mb-6">
                沉浸式
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500">
                  AI 模拟面试
                </span>
                平台
              </h1>

              <p className="text-lg sm:text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
                通过 RAG 检索增强生成技术，为高校学生提供高还原度的技术面试体验。
                上传简历，AI 深度追问，多维度量化评估——助你拿下心仪 Offer。
              </p>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link to="/login">
                  <Button size="lg" className="gap-2 text-base px-8">
                    <FileUp className="h-5 w-5" />
                    立即开始
                  </Button>
                </Link>
                <Link to="/login">
                  <Button variant="outline" size="lg" className="gap-2 text-base px-8">
                    <BarChart3 className="h-5 w-5" />
                    了解更多
                  </Button>
                </Link>
              </div>
            </div>
          </section>

          <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
            <div className="grid md:grid-cols-3 gap-8">
              {features.map((feature) => (
                <div
                  key={feature.title}
                  className="group relative p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-lg transition-all duration-300"
                >
                  <div className="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <feature.icon className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                  <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

const features = [
  {
    icon: Brain,
    title: "简历深度解析",
    description:
      "智能提取 PDF 简历中的核心技术栈与项目关键词，AI 基于真实经历进行针对性追问，彻底告别模板化面试。",
  },
  {
    icon: MessageSquare,
    title: "沉浸式面试体验",
    description:
      "真实模拟面试官对话流程，支持 Markdown 实时渲染。多套面试风格可选：基础技术面、压力面、温和引导面。",
  },
  {
    icon: TrendingUp,
    title: "多维度量化评估",
    description:
      "从技术深度、逻辑表达、专业知识、应变能力、情绪稳定性五个维度输出雷达图，精准定位能力短板。",
  },
];