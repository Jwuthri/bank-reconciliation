import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
  Sequence,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/DMSans";
import { COLORS } from "../styles/theme";
import { FlowNode } from "../components/FlowNode";
import { Caption } from "../components/Caption";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const Arrow: React.FC<{
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  delay: number;
}> = ({ x1, y1, x2, y2, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({ frame, fps, delay, config: { damping: 200 } });
  const opacity = interpolate(progress, [0, 1], [0, 1]);

  return (
    <svg
      style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none" }}
    >
      <defs>
        <marker id={`arrow-${delay}`} markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill={COLORS.lightGreen} opacity={opacity} />
        </marker>
      </defs>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={COLORS.lightGreen}
        strokeWidth={2}
        opacity={opacity}
        markerEnd={`url(#arrow-${delay})`}
      />
    </svg>
  );
};

export const PipelineScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleEnter = spring({ frame, fps, config: { damping: 200 } });
  const titleOpacity = interpolate(titleEnter, [0, 1], [0, 1]);

  const stageLabel = (
    text: string,
    x: number,
    y: number,
    delay: number
  ) => {
    const enter = spring({ frame, fps, delay, config: { damping: 200 } });
    const opacity = interpolate(enter, [0, 1], [0, 1]);
    return (
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          opacity,
          color: COLORS.lightGreen,
          fontSize: 15,
          fontWeight: 700,
          fontFamily: "DM Sans, sans-serif",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        {text}
      </div>
    );
  };

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(145deg, ${COLORS.bgDark} 0%, #0a1a14 100%)`,
        fontFamily,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 50,
          left: 100,
          opacity: titleOpacity,
        }}
      >
        <h2
          style={{
            color: COLORS.white,
            fontSize: 42,
            fontWeight: 700,
            letterSpacing: "-0.02em",
            margin: 0,
          }}
        >
          Two-Stage Pipeline
        </h2>
        <p style={{ color: COLORS.textSecondary, fontSize: 20, marginTop: 6 }}>
          Classify first, then match sequentially -- high confidence first
        </p>
      </div>

      {/* Stage 1: Classification */}
      {stageLabel("Stage 1: Classification", 100, 155, 10)}
      <FlowNode label="Bank Transaction" x={280} y={220} delay={15} variant="secondary" width={240} />
      <Arrow x1={400} y1={248} x2={400} y2={290} delay={20} />
      <FlowNode label="Rule-Based Classifier" x={280} y={320} delay={25} variant="primary" width={240} />

      <Arrow x1={400} y1={348} x2={250} y2={390} delay={35} />
      <Arrow x1={400} y1={348} x2={400} y2={390} delay={35} />
      <Arrow x1={400} y1={348} x2={550} y2={390} delay={35} />

      <FlowNode label="Insurance" x={250} y={420} delay={40} variant="accent" width={180} height={46} fontSize={14} />
      <FlowNode label="Not Insurance" x={430} y={420} delay={45} variant="muted" width={180} height={46} fontSize={14} />
      <FlowNode label="Unknown" x={610} y={420} delay={50} variant="secondary" width={180} height={46} fontSize={14} />

      <Arrow x1={610} y1={443} x2={610} y2={480} delay={55} />
      <FlowNode label="LLM Fallback (gpt-5-mini)" x={610} y={510} delay={58} variant="primary" width={240} height={46} fontSize={14} />

      {/* Stage 2: Matching */}
      {stageLabel("Stage 2: Sequential Matching", 900, 155, 70)}
      <FlowNode label="Insurance Transactions" x={1120} y={220} delay={75} variant="accent" width={280} />
      <Arrow x1={1120} y1={248} x2={1120} y2={290} delay={80} />
      <FlowNode label="PaymentNumberMatcher" x={1120} y={320} delay={85} variant="primary" width={280} />

      {/* Confidence labels */}
      <Sequence from={90} layout="none" premountFor={fps}>
        {(() => {
          const enter = spring({ frame, fps, delay: 90, config: { damping: 200 } });
          const opacity = interpolate(enter, [0, 1], [0, 1]);
          return (
            <div style={{ position: "absolute", left: 1290, top: 305, opacity, color: COLORS.textSecondary, fontSize: 14, fontFamily: "DM Sans, sans-serif" }}>
              TRN extraction<br />Confidence: 1.0 / 0.9
            </div>
          );
        })()}
      </Sequence>

      <Arrow x1={1120} y1={348} x2={1120} y2={400} delay={95} />
      <FlowNode label="Unmatched remainder" x={1120} y={430} delay={98} variant="secondary" width={240} height={46} fontSize={14} />
      <Arrow x1={1120} y1={453} x2={1120} y2={490} delay={102} />
      <FlowNode label="PayerAmountDateMatcher" x={1120} y={520} delay={105} variant="primary" width={280} />

      <Sequence from={110} layout="none" premountFor={fps}>
        {(() => {
          const enter = spring({ frame, fps, delay: 110, config: { damping: 200 } });
          const opacity = interpolate(enter, [0, 1], [0, 1]);
          return (
            <div style={{ position: "absolute", left: 1290, top: 505, opacity, color: COLORS.textSecondary, fontSize: 14, fontFamily: "DM Sans, sans-serif" }}>
              Payer + Amount + Date<br />Confidence: 0.85 / 0.7
            </div>
          );
        })()}
      </Sequence>

      <Arrow x1={1120} y1={548} x2={1120} y2={590} delay={115} />
      <FlowNode label="Reconciled Matches" x={1120} y={620} delay={118} variant="accent" width={260} />

      {/* Big arrow between stages */}
      <Arrow x1={730} y1={320} x2={950} y2={320} delay={72} />

      <Caption
        text="Precision over recall -- false positives erode trust. Better to under-flag than tell a practice their payroll is a missing insurance payment."
        startFrame={130}
      />
    </AbsoluteFill>
  );
};
