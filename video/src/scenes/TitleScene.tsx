import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/DMSans";
import { COLORS } from "../styles/theme";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "700"],
  subsets: ["latin"],
});

export const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleEnter = spring({ frame, fps, config: { damping: 200 } });
  const subtitleEnter = spring({
    frame,
    fps,
    delay: 12,
    config: { damping: 200 },
  });
  const lineEnter = spring({
    frame,
    fps,
    delay: 20,
    config: { damping: 200 },
  });

  const titleOpacity = interpolate(titleEnter, [0, 1], [0, 1]);
  const titleY = interpolate(titleEnter, [0, 1], [40, 0]);
  const subtitleOpacity = interpolate(subtitleEnter, [0, 1], [0, 1]);
  const subtitleY = interpolate(subtitleEnter, [0, 1], [30, 0]);
  const lineWidth = interpolate(lineEnter, [0, 1], [0, 120]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(145deg, ${COLORS.bgDark} 0%, #0a1a14 50%, ${COLORS.darkGreen} 100%)`,
        fontFamily,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          textAlign: "center",
        }}
      >
        <h1
          style={{
            color: COLORS.white,
            fontSize: 72,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            lineHeight: 1.1,
            margin: 0,
          }}
        >
          Lassie Bank Reconciliation
        </h1>
      </div>

      <div
        style={{
          width: lineWidth,
          height: 3,
          background: `linear-gradient(90deg, ${COLORS.lightGreen}, ${COLORS.primaryGreen})`,
          borderRadius: 2,
          marginTop: 28,
          marginBottom: 28,
        }}
      />

      <div
        style={{
          opacity: subtitleOpacity,
          transform: `translateY(${subtitleY}px)`,
          textAlign: "center",
        }}
      >
        <p
          style={{
            color: COLORS.textSecondary,
            fontSize: 30,
            fontWeight: 500,
            letterSpacing: "-0.01em",
            margin: 0,
          }}
        >
          Automated EOB-to-Transaction Matching for Dental Practices
        </p>
      </div>
    </AbsoluteFill>
  );
};
