import { Sun, Moon } from "lucide-react";
import { useAppStore } from "@/store";
import { Button } from "@/components/ui/Button";

export function ThemeToggle() {
  const { theme, toggleTheme } = useAppStore();

  return (
    <Button variant="ghost" size="icon" onClick={toggleTheme} title="切换主题">
      {theme === "dark" ? (
        <Sun className="h-5 w-5" />
      ) : (
        <Moon className="h-5 w-5" />
      )}
    </Button>
  );
}