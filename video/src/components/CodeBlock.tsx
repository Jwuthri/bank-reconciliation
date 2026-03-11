import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { COLORS } from "../styles/theme";

type CodeBlockProps = {
  text: string;
  delay?: number;
  highlight?: string;
  label?: string;
  variant?: "good" | "bad" | "neutral";
};

const VARIANT_COLORS = {
  good: { border: COLORS.lightGreen, labelBg: "rgba(34,197,94,0.15)", labelColor: "#15803d" },
  bad: { border: COLORS.red, labelBg: "rgba(239,68,68,0.12)", labelColor: "#b91c1c" },
  neutral: { border: COLORS.slate, labelBg: "rgba(100,116,139,0.12)", labelColor: COLORS.slate },
};

export const CodeBlock: React.FC<CodeBlockProps> = ({
  text,
  delay = 0,
  highlight,
  label,
  variant = "neutral",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({ frame, fps, delay, config: { damping: 200 } });
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const translateX = interpolate(enter, [0, 1], [-30, 0]);
  const colors = VARIANT_COLORS[variant];

  let rendered: React.ReactNode = text;
  if (highlight) {
    const idx = text.indexOf(highlight);
    if (idx >= 0) {
      rendered = (
        <>
          {text.slice(0, idx)}
          <span
            style={{
              background: "rgba(34,197,94,0.25)",
              borderRadius: 4,
              padding: "2px 4px",
              color: "#86efac",
            }}
          >
            {highlight}
          </span>
          {text.slice(idx + highlight.length)}
        </>
      );
    }
  }

  return (
    <div
      style={{
        opacity,
        transform: `translateX(${translateX}px)`,
        display: "flex",
        alignItems: "center",
        gap: 16,
        marginBottom: 14,
      }}
    >
      {label && (
        <span
          style={{
            background: colors.labelBg,
            color: colors.labelColor,
            fontSize: 14,
            fontWeight: 700,
            padding: "6px 14px",
            borderRadius: 20,
            fontFamily: "DM Sans, sans-serif",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </span>
      )}
      <div
        style={{
          background: "#1a2e28",
          borderLeft: `4px solid ${colors.border}`,
          borderRadius: 8,
          padding: "14px 22px",
          flex: 1,
        }}
      >
        <code
          style={{
            color: "#e8efeb",
            fontSize: 20,
            fontFamily: "JetBrains Mono, monospace",
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
          }}
        >
          {rendered}
        </code>
      </div>
    </div>
  );
};
