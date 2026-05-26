import { Link } from "react-router-dom";
import {
  Brain,
  FileUp,
  MessageSquare,
  BarChart3,
  Zap,
  Shield,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function Home() {
  return (
    <div className="min-h-[calc(100vh-4rem)]">
      {/* Hero Section */}
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
            <Link to="/upload">
              <Button size="lg" className="gap-2 text-base px-8">
                <FileUp className="h-5 w-5" />
                上传简历，开始面试
              </Button>
            </Link>
            <Link to="/report">
              <Button variant="outline" size="lg" className="gap-2 text-base px-8">
                <BarChart3 className="h-5 w-5" />
                查看示例报告
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
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