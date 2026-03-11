import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { COLORS } from "../styles/theme";

type BarItem = {
  label: string;
  value: number;
  total: number;
  color: string;
};

type BarChartProps = {
  bars: BarItem[];
  delay?: number;
  maxWidth?: number;
};

export const BarChart: React.FC<BarChartProps> = ({
  bars,
  delay = 0,
  maxWidth = 900,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28, width: maxWidth }}>
      {bars.map((bar, i) => {
        const progress = spring({
          frame,
          fps,
          delay: delay + i * 8,
          config: { damping: 200 },
          durationInFrames: 40,
        });

        const pct = (bar.value / bar.total) * 100;
        const width = interpolate(progress, [0, 1], [0, pct]);
        const currentVal = Math.round(
          interpolate(progress, [0, 1], [0, bar.value])
        );
        const opacity = interpolate(progress, [0, 0.3], [0, 1], {
          extrapolateRight: "clamp",
        });

        return (
          <div key={bar.label} style={{ opacity }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  color: COLORS.white,
                  fontSize: 22,
                  fontWeight: 600,
                  fontFamily: "DM Sans, sans-serif",
                }}
              >
                {bar.label}
              </span>
              <span
                style={{
                  color: COLORS.white,
                  fontSize: 22,
                  fontWeight: 700,
                  fontFamily: "DM Sans, sans-serif",
                }}
              >
                {currentVal.toLocaleString()} / {bar.total.toLocaleString()} (
                {Math.round(width)}%)
              </span>
            </div>
            <div
              style={{
                height: 20,
                background: "rgba(255,255,255,0.1)",
                borderRadius: 10,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${width}%`,
                  background: `linear-gradient(90deg, ${bar.color}, ${bar.color}cc)`,
                  borderRadius: 10,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};
