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
import { Caption } from "../components/Caption";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "600", "700"],
  subsets: ["latin"],
});
const { fontFamily: monoFamily } = loadMono("normal", {
  weights: ["400", "500"],
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

export const PayerAmountScene: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(145deg, ${COLORS.bgDark} 0%, #0a1a14 100%)`,
        fontFamily,
        padding: "50px 100px",
      }}
    >
      <FadeIn delay={0}>
        <h2 style={{ color: COLORS.white, fontSize: 42, fontWeight: 700, letterSpacing: "-0.02em", margin: "0 0 6px 0" }}>
          PayerAmountDateMatcher
        </h2>
        <p style={{ color: COLORS.textSecondary, fontSize: 20, margin: "0 0 30px 0" }}>
          Fuzzy matching when no payment reference exists -- payer name + amount + date window
        </p>
      </FadeIn>

      {/* Bank transaction */}
      <FadeIn delay={15}>
        <div style={{ color: COLORS.lightGreen, fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
          Bank Transaction
        </div>
        <div
          style={{
            background: "#1a2e28",
            borderRadius: 10,
            padding: "16px 28px",
            borderLeft: `4px solid ${COLORS.primaryGreen}`,
            marginBottom: 28,
            display: "flex",
            gap: 50,
          }}
        >
          <div>
            <div style={{ color: COLORS.textSecondary, fontSize: 13, marginBottom: 4 }}>Note</div>
            <code style={{ fontFamily: monoFamily, fontSize: 24, color: "#86efac" }}>"MetLife"</code>
          </div>
          <div>
            <div style={{ color: COLORS.textSecondary, fontSize: 13, marginBottom: 4 }}>Amount</div>
            <code style={{ fontFamily: monoFamily, fontSize: 24, color: "#fcd34d" }}>$241.20</code>
          </div>
          <div>
            <div style={{ color: COLORS.textSecondary, fontSize: 13, marginBottom: 4 }}>Date</div>
            <code style={{ fontFamily: monoFamily, fontSize: 24, color: "#e8efeb" }}>Sep 9, 2025</code>
          </div>
        </div>
      </FadeIn>

      {/* Matching steps */}
      <Sequence from={40} layout="none" premountFor={30}>
        <FadeIn delay={40}>
          <div style={{ color: COLORS.lightGreen, fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Step 1: Identify payer from note (case-insensitive)
          </div>
          <div style={{ background: "#1a2e28", borderRadius: 10, padding: "14px 28px", borderLeft: `4px solid ${COLORS.amber}`, marginBottom: 24, display: "flex", gap: 30, alignItems: "center" }}>
            <code style={{ fontFamily: monoFamily, fontSize: 20, color: "#e8efeb" }}>
              "MetLife" → <span style={{ color: "#86efac" }}>payer_id = 3 (MetLife)</span>
            </code>
          </div>
        </FadeIn>
      </Sequence>

      <Sequence from={70} layout="none" premountFor={30}>
        <FadeIn delay={70}>
          <div style={{ color: COLORS.lightGreen, fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Step 2: Find EOBs matching payer + amount within ±14-day window
          </div>
          <div style={{ background: "#1a2e28", borderRadius: 10, padding: "14px 28px", borderLeft: `4px solid ${COLORS.amber}`, marginBottom: 24 }}>
            <code style={{ fontFamily: monoFamily, fontSize: 18, color: "#e8efeb", lineHeight: 1.8 }}>
              {"SELECT * FROM eobs\n"}
              {"WHERE payer_id = 3\n"}
              {"  AND adjusted_amount = 24120\n"}
              {"  AND ABS(payment_date - 'Sep 9') <= 14 days\n"}
              <span style={{ color: "#86efac" }}>→ 1 candidate found (EOB #29, Sep 5)</span>
            </code>
          </div>
        </FadeIn>
      </Sequence>

      <Sequence from={110} layout="none" premountFor={30}>
        <FadeIn delay={110}>
          <div style={{ color: COLORS.lightGreen, fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
            Step 3: Confidence scoring
          </div>
          <div style={{ display: "flex", gap: 24 }}>
            <div style={{ background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.3)", borderRadius: 10, padding: "14px 24px", textAlign: "center" }}>
              <div style={{ color: "#86efac", fontSize: 36, fontWeight: 700 }}>0.85</div>
              <div style={{ color: COLORS.textSecondary, fontSize: 14, marginTop: 4 }}>Single candidate</div>
            </div>
            <div style={{ background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.3)", borderRadius: 10, padding: "14px 24px", textAlign: "center" }}>
              <div style={{ color: "#fcd34d", fontSize: 36, fontWeight: 700 }}>0.70</div>
              <div style={{ color: COLORS.textSecondary, fontSize: 14, marginTop: 4 }}>Multiple candidates (closest date)</div>
            </div>
          </div>
        </FadeIn>
      </Sequence>

      <Caption
        text="~844 matches. No reference number -- we rely on payer + amount + date window. Ambiguous cases get lower confidence for manual review."
        startFrame={140}
      />
    </AbsoluteFill>
  );
};
