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

    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current);
    }

    const isDark = theme === "dark";
    const textColor = isDark ? "#94a3b8" : "#64748b";
    const axisColor = isDark ? "#334155" : "#e2e8f0";

    const filteredEntries = Object.entries(data).filter(([, v]) => typeof v === "number");
    const indicators = filteredEntries.map(([name]) => ({ name, max: 100 }));
    const values = filteredEntries.map(([, value]) => value as number);

    const avg = values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : 0;
    const mainColor = avg >= 80 ? "#10b981" : avg >= 60 ? "#3b82f6" : avg >= 40 ? "#f59e0b" : "#ef4444";
    const areaStart = avg >= 80 ? "rgba(16,185,129,0.35)" : avg >= 60 ? "rgba(59,130,246,0.35)" : avg >= 40 ? "rgba(245,158,11,0.35)" : "rgba(239,68,68,0.35)";
    const areaEnd = avg >= 80 ? "rgba(16,185,129,0.03)" : avg >= 60 ? "rgba(59,130,246,0.03)" : avg >= 40 ? "rgba(245,158,11,0.03)" : "rgba(239,68,68,0.03)";

    instanceRef.current.setOption(
      {
        tooltip: {
          trigger: "item",
          backgroundColor: isDark ? "#1e293b" : "#fff",
          borderColor: axisColor,
          textStyle: { color: textColor },
          formatter: (params: any) => {
            if (!params.value) return "";
            const names = filteredEntries.map(([n]) => n);
            const vals = params.value as number[];
            let html = `<div style="font-weight:600;margin-bottom:6px">能力评估</div>`;
            names.forEach((name, i) => {
              const v = vals[i] ?? 0;
              const color = v >= 80 ? "#10b981" : v >= 60 ? "#3b82f6" : v >= 40 ? "#f59e0b" : "#ef4444";
              html += `<div style="display:flex;justify-content:space-between;gap:16px"><span>${name}</span><span style="color:${color};font-weight:600">${v}</span></div>`;
            });
            return html;
          },
        },
        legend: { show: false },
        radar: {
          center: ["50%", "52%"],
          radius: "68%",
          indicator: indicators,
          startAngle: 90,
          axisName: {
            color: textColor,
            fontSize: 12,
            fontWeight: 500,
            padding: [3, 5],
          },
          axisLine: { lineStyle: { color: axisColor, width: 1 } },
          splitLine: { lineStyle: { color: axisColor, width: 1 } },
          splitArea: {
            show: true,
            areaStyle: {
              color: [
                isDark ? "rgba(59,130,246,0.04)" : "rgba(59,130,246,0.02)",
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
                symbol: "circle",
                symbolSize: 6,
                areaStyle: {
                  color: {
                    type: "linear",
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                      { offset: 0, color: areaStart },
                      { offset: 1, color: areaEnd },
                    ],
                  },
                },
                lineStyle: {
                  color: mainColor,
                  width: 2.5,
                  shadowColor: mainColor,
                  shadowBlur: 8,
                },
                itemStyle: {
                  color: mainColor,
                  borderColor: "#fff",
                  borderWidth: 2,
                  shadowColor: mainColor,
                  shadowBlur: 6,
                },
                label: {
                  show: true,
                  formatter: (params: any) => `${params.value}`,
                  fontSize: 11,
                  fontWeight: 600,
                  color: mainColor,
                },
              },
            ],
          },
        ],
      },
      true
    );

    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener("resize", handleResize);

    return () => window.removeEventListener("resize", handleResize);
  }, [data, theme]);

  return (
    <div
      ref={chartRef}
      className="w-full"
      style={{ height: 400 }}
    />
  );
}
