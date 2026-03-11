import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import { COLORS } from "../styles/theme";

type CaptionProps = {
  text: string;
  startFrame?: number;
};

export const Caption: React.FC<CaptionProps> = ({ text, startFrame = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = frame - startFrame;

  if (localFrame < 0) return null;

  const enter = spring({ frame: localFrame, fps, config: { damping: 200 } });
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const translateY = interpolate(enter, [0, 1], [20, 0]);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 60,
        left: 80,
        right: 80,
        display: "flex",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: COLORS.captionBg,
          backdropFilter: "blur(12px)",
          borderRadius: 12,
          padding: "18px 36px",
          opacity,
          transform: `translateY(${translateY}px)`,
          maxWidth: 1400,
        }}
      >
        <span
          style={{
            color: COLORS.white,
            fontSize: 26,
            fontFamily: "DM Sans, sans-serif",
            fontWeight: 500,
            lineHeight: 1.5,
            letterSpacing: "-0.01em",
          }}
        >
          {text}
        </span>
      </div>
    </div>
  );
};
