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
import { BarChart } from "../components/BarChart";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const FadeIn: React.FC<{
  delay: number;
  children: React.ReactNode;
}> = ({ delay, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, delay, config: { damping: 200 } });
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const translateY = interpolate(enter, [0, 1], [20, 0]);
  return <div style={{ opacity, transform: `translateY(${translateY}px)` }}>{children}</div>;
};

export const ResultsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const closingEnter = spring({
    frame,
    fps,
    delay: durationInFrames - 90,
    config: { damping: 200 },
  });
  const closingOpacity = interpolate(closingEnter, [0, 1], [0, 1]);
  const closingScale = interpolate(closingEnter, [0, 1], [0.9, 1]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(145deg, ${COLORS.bgDark} 0%, #0a1a14 100%)`,
        fontFamily,
        padding: "50px 100px",
      }}
    >
      <FadeIn delay={0}>
        <h2 style={{ color: COLORS.white, fontSize: 42, fontWeight: 700, letterSpacing: "-0.02em", margin: "0 0 30px 0" }}>
          Results
        </h2>
      </FadeIn>

      <Sequence from={10} layout="none" premountFor={30}>
        <BarChart
          delay={15}
          bars={[
            { label: "EOB Match Rate", value: 3293, total: 3526, color: COLORS.lightGreen },
            { label: "Insurance Txn Match Rate", value: 2839, total: 5238, color: COLORS.amber },
          ]}
        />
      </Sequence>

      <Sequence from={70} layout="none" premountFor={30}>
        <FadeIn delay={70}>
          <div style={{ marginTop: 40, background: "rgba(255,255,255,0.05)", borderRadius: 12, padding: "20px 28px", borderLeft: `4px solid ${COLORS.amber}` }}>
            <div style={{ color: COLORS.white, fontSize: 22, fontWeight: 600, marginBottom: 6 }}>
              Key Insight
            </div>
            <div style={{ color: COLORS.textSecondary, fontSize: 18, lineHeight: 1.6 }}>
              Main gap: 1,677 TRN payment numbers exist in bank notes but not in EOB data -- a data alignment issue upstream, not a code limitation.
            </div>
          </div>
        </FadeIn>
      </Sequence>

      <Sequence from={120} layout="none" premountFor={30}>
        <FadeIn delay={120}>
          <div style={{ marginTop: 28 }}>
            <div style={{ color: COLORS.lightGreen, fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
              Roadmap
            </div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {[
                "Constraint relaxation (date window, amount tolerance)",
                "HCCLAIMPMT payer code mapping",
                "Adaptive payer-specific date windows",
                "Scheduled reconciliation + audit trail",
              ].map((item, i) => {
                const itemEnter = spring({ frame, fps, delay: 130 + i * 8, config: { damping: 200 } });
                const itemOpacity = interpolate(itemEnter, [0, 1], [0, 1]);
                return (
                  <div
                    key={i}
                    style={{
                      opacity: itemOpacity,
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      borderRadius: 8,
                      padding: "10px 18px",
                      color: COLORS.white,
                      fontSize: 16,
                      fontWeight: 500,
                    }}
                  >
                    {item}
                  </div>
                );
              })}
            </div>
          </div>
        </FadeIn>
      </Sequence>

      {/* Closing card */}
      <div
        style={{
          position: "absolute",
          bottom: 50,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          opacity: closingOpacity,
          transform: `scale(${closingScale})`,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ color: COLORS.white, fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em" }}>
            Lassie
          </div>
          <div style={{ color: COLORS.textSecondary, fontSize: 18, marginTop: 4 }}>
            Reconciliation that earns trust.
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
