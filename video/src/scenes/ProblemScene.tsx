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
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { COLORS } from "../styles/theme";
import { AnimatedCounter } from "../components/AnimatedCounter";
import { CodeBlock } from "../components/CodeBlock";
import { Caption } from "../components/Caption";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "700"],
  subsets: ["latin"],
});
loadMono("normal", { weights: ["400", "500"], subsets: ["latin"] });

export const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headlineEnter = spring({ frame, fps, config: { damping: 200 } });
  const headlineOpacity = interpolate(headlineEnter, [0, 1], [0, 1]);
  const headlineY = interpolate(headlineEnter, [0, 1], [30, 0]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(145deg, ${COLORS.bgDark} 0%, #0a1a14 100%)`,
        fontFamily,
        padding: "60px 100px",
      }}
    >
      <div
        style={{
          opacity: headlineOpacity,
          transform: `translateY(${headlineY}px)`,
          marginBottom: 20,
        }}
      >
        <h2
          style={{
            color: COLORS.white,
            fontSize: 46,
            fontWeight: 700,
            letterSpacing: "-0.02em",
            margin: 0,
          }}
        >
          The Problem
        </h2>
      </div>

      <div
        style={{
          display: "flex",
          gap: 60,
          marginBottom: 36,
          marginTop: 10,
        }}
      >
        <Sequence from={10} layout="none" premountFor={fps}>
          <div style={{ textAlign: "center" }}>
            <AnimatedCounter
              value={8611}
              delay={10}
              fontSize={56}
              color={COLORS.white}
            />
            <div
              style={{
                color: COLORS.textSecondary,
                fontSize: 18,
                marginTop: 4,
              }}
            >
              Bank Transactions
            </div>
          </div>
        </Sequence>
        <Sequence from={18} layout="none" premountFor={fps}>
          <div style={{ textAlign: "center" }}>
            <AnimatedCounter
              value={3526}
              delay={18}
              fontSize={56}
              color={COLORS.white}
            />
            <div
              style={{
                color: COLORS.textSecondary,
                fontSize: 18,
                marginTop: 4,
              }}
            >
              EOBs
            </div>
          </div>
        </Sequence>
        <Sequence from={26} layout="none" premountFor={fps}>
          <div style={{ textAlign: "center" }}>
            <AnimatedCounter
              value={26}
              delay={26}
              fontSize={56}
              color={COLORS.white}
            />
            <div
              style={{
                color: COLORS.textSecondary,
                fontSize: 18,
                marginTop: 4,
              }}
            >
              Insurance Payers
            </div>
          </div>
        </Sequence>
      </div>

      <Sequence from={40} layout="none" premountFor={fps}>
        <div style={{ marginTop: 8 }}>
          <div
            style={{
              color: COLORS.textSecondary,
              fontSize: 18,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 16,
            }}
          >
            What bank transaction notes look like:
          </div>
          <CodeBlock
            text='HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\'
            delay={45}
            label="Signal"
            variant="good"
          />
          <CodeBlock
            text='"MetLife"'
            delay={55}
            label="Vague"
            variant="neutral"
          />
          <CodeBlock
            text='"PAYROLL"  /  "rent"  /  "Porsche payment"'
            delay={65}
            label="Noise"
            variant="bad"
          />
        </div>
      </Sequence>

      <Caption
        text="Transaction notes range from structured clearinghouse references to completely unrelated business expenses. The engine must separate signal from noise."
        startFrame={80}
      />
    </AbsoluteFill>
  );
};
