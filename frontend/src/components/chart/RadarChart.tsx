import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { useAppStore } from "@/store";
import type { RadarScores } from "@/types";

interface RadarChartProps {
  data: Record<string, number> | RadarScores;
}

export function RadarChart({ data }: RadarChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);
  const { theme } = useAppStore();

  useEffect(() => {
    if (!chartRef.current) return;

    // 初始化或复用实例
    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current);
    }

    const isDark = theme === "dark";
    const textColor = isDark ? "#94a3b8" : "#64748b";
    const axisColor = isDark ? "#334155" : "#e2e8f0";

    const indicators = Object.entries(data).map(([name]) => ({
      name,
      max: 100,
    }));

    const values = Object.entries(data).map(([, value]) => value);

    instanceRef.current.setOption(
      {
        tooltip: {
          trigger: "item",
          backgroundColor: isDark ? "#1e293b" : "#fff",
          borderColor: axisColor,
          textStyle: { color: textColor },
        },
        legend: { show: false },
        radar: {
          center: ["50%", "50%"],
          radius: "70%",
          indicator: indicators,
          axisName: {
            color: textColor,
            fontSize: 12,
          },
          axisLine: { lineStyle: { color: axisColor } },
          splitLine: { lineStyle: { color: axisColor } },
          splitArea: {
            areaStyle: {
              color: [
                isDark ? "rgba(59,130,246,0.05)" : "rgba(59,130,246,0.03)",
                "transparent",
              ],
            },
          },
        },
        series: [
          {
            type: "radar",
            data: [
              {
                value: values,
                name: "你的得分",
                areaStyle: {
                  color: {
                    type: "linear",
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                      { offset: 0, color: "rgba(37,99,235,0.35)" },
                      { offset: 1, color: "rgba(37,99,235,0.05)" },
                    ],
                  },
                },
                lineStyle: {
                  color: "#2563eb",
                  width: 2,
                },
                itemStyle: {
                  color: "#2563eb",
                },
              },
            ],
          },
        ],
      },
      true
    );

    // 响应式调整
    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener("resize", handleResize);

    return () => window.removeEventListener("resize", handleResize);
  }, [data, theme]);

  return (
    <div
      ref={chartRef}
      className="w-full"
      style={{ height: 380 }}
    />
  );
}