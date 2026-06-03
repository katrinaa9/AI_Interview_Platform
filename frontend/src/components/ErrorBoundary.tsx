import { Component, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = "/";
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center px-4 bg-white dark:bg-gray-950">
          <div className="max-w-md w-full text-center">
            <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/40 flex items-center justify-center mx-auto mb-6">
              <AlertTriangle className="h-8 w-8 text-red-500" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">
              页面出现异常
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
              应用遇到了意外错误，请尝试刷新页面
            </p>
            {this.state.error && (
              <p className="text-xs text-slate-400 dark:text-slate-500 mb-6 font-mono bg-slate-100 dark:bg-slate-800 rounded-lg p-3 max-h-32 overflow-y-auto">
                {this.state.error.message}
              </p>
            )}
            <Button onClick={this.handleReset} className="gap-2">
              <RotateCcw className="h-4 w-4" />
              返回首页
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
