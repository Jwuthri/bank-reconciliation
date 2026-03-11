import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { COLORS } from "../styles/theme";

type FlowNodeProps = {
  label: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  delay?: number;
  variant?: "primary" | "secondary" | "accent" | "muted";
  fontSize?: number;
};

const VARIANT_STYLES = {
  primary: { bg: COLORS.primaryGreen, text: COLORS.white, border: COLORS.darkGreen },
  secondary: { bg: COLORS.white, text: COLORS.darkGreen, border: COLORS.primaryGreen },
  accent: { bg: COLORS.lightGreen, text: COLORS.darkGreen, border: "#16a34a" },
  muted: { bg: "#f1f5f3", text: COLORS.textSecondary, border: "#d1ddd7" },
};

export const FlowNode: React.FC<FlowNodeProps> = ({
  label,
  x,
  y,
  width = 260,
  height = 56,
  delay = 0,
  variant = "secondary",
  fontSize = 16,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({
    frame,
    fps,
    delay,
    config: { damping: 200 },
  });

  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const scale = interpolate(enter, [0, 1], [0.85, 1]);
  const style = VARIANT_STYLES[variant];

  return (
    <div
      style={{
        position: "absolute",
        left: x - width / 2,
        top: y - height / 2,
        width,
        height,
        background: style.bg,
        border: `2px solid ${style.border}`,
        borderRadius: 10,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity,
        transform: `scale(${scale})`,
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      }}
    >
      <span
        style={{
          color: style.text,
          fontSize,
          fontWeight: 600,
          fontFamily: "DM Sans, sans-serif",
          textAlign: "center",
          padding: "0 12px",
        }}
      >
        {label}
      </span>
    </div>
  );
};
