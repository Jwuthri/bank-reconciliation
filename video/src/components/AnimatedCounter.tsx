import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

type AnimatedCounterProps = {
  value: number;
  prefix?: string;
  suffix?: string;
  delay?: number;
  fontSize?: number;
  color?: string;
  fontWeight?: number;
};

export const AnimatedCounter: React.FC<AnimatedCounterProps> = ({
  value,
  prefix = "",
  suffix = "",
  delay = 0,
  fontSize = 64,
  color = "#1a2e28",
  fontWeight = 700,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame,
    fps,
    delay,
    config: { damping: 200 },
    durationInFrames: 40,
  });

  const current = Math.round(interpolate(progress, [0, 1], [0, value]));
  const formatted = current.toLocaleString();

  return (
    <span
      style={{
        fontSize,
        fontWeight,
        color,
        fontFamily: "DM Sans, sans-serif",
        letterSpacing: "-0.03em",
      }}
    >
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
};
