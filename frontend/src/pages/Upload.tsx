import { useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Upload as UploadIcon, FileText, X, Check, Loader2, ArrowRight, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/store";
import { cn } from "@/lib/utils";

const MOCK_TECH_TAGS = [
  "React", "Vue", "Angular", "TypeScript", "JavaScript",
  "Node.js", "FastAPI", "Django", "Spring Boot", "Golang",
  "MySQL", "PostgreSQL", "MongoDB", "Redis", "Docker",
  "Kubernetes", "AWS", "Linux", "Git", "CI/CD",
  "Python", "Java", "C++", "Rust", "机器学习",
];

export default function Upload() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { setKeywords, token, resetInterview } = useAppStore();

  const [file, setFile] = useState<File | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [parsedKeywords, setParsedKeywords] = useState<string[]>([]);
  const [parseMessage, setParseMessage] = useState("");
  const [showFallback, setShowFallback] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [customInput, setCustomInput] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false); // 防重复提交

  // ===== 通过 POST /api/resume/upload 上传并解析 =====
  const handleParse = useCallback(async (uploadFile: File) => {
    if (isSubmitting) return; // 防重复提交
    setIsSubmitting(true);
    setIsParsing(true);
    setShowFallback(false);
    setErrorMsg("");
    setParseMessage("");

    try {
      const formData = new FormData();
      formData.append("file", uploadFile);

      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("/api/resume/upload", {
        method: "POST",
        headers,
        body: formData,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `服务器错误 (${res.status})`);
      }

      const data = await res.json();

      if (data.parsed_keywords && data.parsed_keywords.length > 0) {
        // 解析成功
        setParsedKeywords(data.parsed_keywords);
        setParseMessage(data.message || "简历解析成功");
        setShowFallback(false);
      } else {
        // 解析成功但无关键词，触发降级
        setParsedKeywords([]);
        setParseMessage(data.message || "未识别到技术栈关键词");
        setShowFallback(true);
      }
    } catch (err: any) {
      console.error("简历解析失败:", err);
      setErrorMsg(err.message || "网络异常，请稍后重试");
      setParsedKeywords([]);
      setShowFallback(true);
    } finally {
      setIsParsing(false);
      setIsSubmitting(false);
    }
  }, [token, isSubmitting]);

  // 拖拽上传
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      if (!droppedFile.name.toLowerCase().endsWith(".pdf")) {
        setErrorMsg("仅支持 PDF 格式的简历文件");
        return;
      }
      if (droppedFile.size > 10 * 1024 * 1024) {
        setErrorMsg("文件大小不能超过 10MB");
        return;
      }
      setFile(droppedFile);
      setErrorMsg("");
      handleParse(droppedFile);
    }
  }, [handleParse]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (selected.size > 10 * 1024 * 1024) {
        setErrorMsg("文件大小不能超过 10MB");
        return;
      }
      setFile(selected);
      setErrorMsg("");
      handleParse(selected);
    }
  };

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const addCustomTag = () => {
    const trimmed = customInput.trim();
    if (trimmed && !selectedTags.includes(trimmed)) {
      setSelectedTags((prev) => [...prev, trimmed]);
      setCustomInput("");
    }
  };

  // ===== 继续：提交关键词到后端并跳转面试间 =====
  const handleContinue = async () => {
    if (isSubmitting) return; // 防重复提交

    const finalKeywords = showFallback ? selectedTags : parsedKeywords;

    if (finalKeywords.length === 0) return;

    setIsSubmitting(true);

    // 降级模式下，先提交关键词到后端
    if (showFallback) {
      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        await fetch("/api/resume/keywords", {
          method: "POST",
          headers,
          body: JSON.stringify({ keywords: finalKeywords }),
        });
      } catch (err) {
        console.error("关键词提交失败:", err);
        // 不阻断流程，前端仍然保存关键词
      }
    }

    resetInterview();
    setKeywords(finalKeywords);
    navigate("/interview");
  };

  const handleReset = () => {
    setFile(null);
    setParsedKeywords([]);
    setShowFallback(false);
    setErrorMsg("");
    setParseMessage("");
    setSelectedTags([]);
    setCustomInput("");
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-12 sm:px-6 lg:px-8">
      {/* 标题 */}
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold mb-3">上传你的简历</h1>
        <p className="text-slate-600 dark:text-slate-400">
          支持 PDF 格式，AI 将自动提取核心技术栈进行深度面试
        </p>
      </div>

      {/* 错误提示 */}
      {errorMsg && !file && (
        <div className="mb-6 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {errorMsg}
        </div>
      )}

      {/* 拖拽上传区 */}
      {!file && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            "relative border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all",
            "border-slate-300 dark:border-slate-700 hover:border-blue-400 dark:hover:border-blue-500",
            "bg-slate-50 dark:bg-gray-900/50 hover:bg-blue-50/50 dark:hover:bg-blue-950/30"
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={handleFileSelect}
          />
          <UploadIcon className="h-16 w-16 mx-auto mb-4 text-slate-400 dark:text-slate-600" />
          <h3 className="text-lg font-semibold mb-2">拖拽 PDF 文件到此处</h3>
          <p className="text-sm text-slate-500 dark:text-slate-500">
            或点击此处选择文件（最大 10MB）
          </p>
        </div>
      )}

      {/* 解析状态区 */}
      {file && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-gray-900 p-8">
          {/* 文件信息 */}
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                <FileText className="h-5 w-5 text-red-500" />
              </div>
              <div>
                <p className="font-medium">{file.name}</p>
                <p className="text-sm text-slate-500">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
            <button
              onClick={handleReset}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* 解析中——进度条 */}
          {isParsing && (
            <div className="space-y-3 animate-fade-in">
              <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在上传并解析简历，提取关键技术栈...
              </div>
              <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 animate-pulse rounded-full w-2/3" />
              </div>
            </div>
          )}

          {/* 解析出错 */}
          {!isParsing && errorMsg && (
            <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm flex items-center gap-2 mb-4">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {errorMsg}
            </div>
          )}

          {/* 解析成功：展示关键词 */}
          {!isParsing && !showFallback && (
            <div className="space-y-4 animate-fade-in">
              <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                <Check className="h-4 w-4" />
                {parseMessage || "简历解析完成"}
              </div>
              <div className="flex flex-wrap gap-2">
                {parsedKeywords.map((kw) => (
                  <span
                    key={kw}
                    className="px-3 py-1.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-sm font-medium"
                  >
                    {kw}
                  </span>
                ))}
              </div>
              <Button onClick={handleContinue} className="gap-2 mt-2" disabled={parsedKeywords.length === 0}>
                开始面试
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          )}

          {/* 降级模式：手动选择关键词 */}
          {!isParsing && showFallback && (
            <div className="space-y-4 animate-fade-in">
              <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 text-sm flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {parseMessage || "简历中包含复杂排版，无法自动解析。请手动选择你的核心技术栈："}
              </div>

              <div className="flex flex-wrap gap-2">
                {MOCK_TECH_TAGS.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => toggleTag(tag)}
                    className={cn(
                      "px-3 py-1.5 rounded-full text-sm font-medium transition-all",
                      selectedTags.includes(tag)
                        ? "bg-blue-600 text-white"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                    )}
                  >
                    {tag}
                  </button>
                ))}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={customInput}
                  onChange={(e) => setCustomInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addCustomTag()}
                  placeholder="输入自定义技术标签..."
                  className="flex-1 h-10 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-gray-800 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <Button variant="outline" size="sm" onClick={addCustomTag}>
                  添加
                </Button>
              </div>

              {selectedTags.length > 0 && (
                <Button onClick={handleContinue} className="gap-2 mt-2">
                  确认技术栈，开始面试
                  <ArrowRight className="h-4 w-4" />
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}