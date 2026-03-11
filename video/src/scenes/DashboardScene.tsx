import React from "react";
import {
  AbsoluteFill,
  Sequence,
  Video,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/DMSans";
import { COLORS } from "../styles/theme";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const SectionLabel: React.FC<{
  text: string;
  subtitle: string;
  delay: number;
}> = ({ text, subtitle, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, delay, config: { damping: 200 } });
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const translateY = interpolate(enter, [0, 1], [15, 0]);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 40,
        left: 60,
        right: 60,
        display: "flex",
        justifyContent: "center",
        zIndex: 10,
      }}
    >
      <div
        style={{
          background: COLORS.captionBg,
          backdropFilter: "blur(12px)",
          borderRadius: 12,
          padding: "16px 32px",
          opacity,
          transform: `translateY(${translateY}px)`,
          maxWidth: 1400,
          textAlign: "center",
        }}
      >
        <div style={{ color: COLORS.lightGreen, fontSize: 15, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
          {text}
        </div>
        <div style={{ color: COLORS.white, fontSize: 22, fontWeight: 500, lineHeight: 1.4 }}>
          {subtitle}
        </div>
      </div>
    </div>
  );
};

export const DashboardScene: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: COLORS.bgDark, fontFamily }}>
      {/* Overview recording */}
      <Sequence from={0} durationInFrames={240} premountFor={30}>
        <AbsoluteFill>
          <Video
            src={staticFile("overview.webm")}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          <SectionLabel
            text="Overview"
            subtitle="Classification and reconciliation KPIs at a glance. 8,611 transactions classified, 2,839 matched to EOBs."
            delay={15}
          />
        </AbsoluteFill>
      </Sequence>

      {/* Payments recording */}
      <Sequence from={240} durationInFrames={300} premountFor={30}>
        <AbsoluteFill>
          <Video
            src={staticFile("payments.webm")}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          <SectionLabel
            text="Payments"
            subtitle="Click any row to inspect the full match chain -- EOB data, bank transaction, confidence score, and match method."
            delay={15}
          />
        </AbsoluteFill>
      </Sequence>

      {/* Inbox recording */}
      <Sequence from={540} durationInFrames={210} premountFor={30}>
        <AbsoluteFill>
          <Video
            src={staticFile("inbox.webm")}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          <SectionLabel
            text="Inbox"
            subtitle="Follow-up tasks for the practice: manually link unresolved items or dismiss false positives."
            delay={15}
          />
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};
