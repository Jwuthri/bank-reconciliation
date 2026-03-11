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
  translateY?: number;
}> = ({ delay, children, translateY: ty = 20 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, delay, config: { damping: 200 } });
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const translateY = interpolate(enter, [0, 1], [ty, 0]);
  return <div style={{ opacity, transform: `translateY(${translateY}px)` }}>{children}</div>;
};

export const PaymentNumberScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const noteText = 'HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\';
  const trnPart = "TRN*1*";
  const paymentNum = "736886274";
  const afterTrn = "*1470858530\\";

  const highlightProgress = spring({
    frame,
    fps,
    delay: 40,
    config: { damping: 200 },
  });
  const highlightOpacity = interpolate(highlightProgress, [0, 1], [0, 1]);

  const extractProgress = spring({
    frame,
    fps,
    delay: 70,
    config: { damping: 20, stiffness: 200 },
  });
  const extractScale = interpolate(extractProgress, [0, 1], [1, 1.15]);
  const extractGlow = interpolate(extractProgress, [0, 1], [0, 1]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(145deg, ${COLORS.bgDark} 0%, #0a1a14 100%)`,
        fontFamily,
        padding: "50px 100px",
      }}
    >
      <FadeIn delay={0}>
        <h2
          style={{
            color: COLORS.white,
            fontSize: 42,
            fontWeight: 700,
            letterSpacing: "-0.02em",
            margin: "0 0 6px 0",
          }}
        >
          PaymentNumberMatcher
        </h2>
        <p style={{ color: COLORS.textSecondary, fontSize: 20, margin: "0 0 30px 0" }}>
          Extracts TRN payment number from bank note, looks up EOB by exact payment_number
        </p>
      </FadeIn>

      {/* Step 1: Bank note */}
      <FadeIn delay={15}>
        <div style={{ color: COLORS.lightGreen, fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
          Step 1: Parse bank transaction note
        </div>
        <div
          style={{
            background: "#1a2e28",
            borderRadius: 10,
            padding: "18px 28px",
            borderLeft: `4px solid ${COLORS.primaryGreen}`,
            marginBottom: 30,
          }}
        >
          <code style={{ fontFamily: monoFamily, fontSize: 22, color: "#e8efeb", lineHeight: 1.6 }}>
            {"HCCLAIMPMT ZP UHCDComm5044 "}
            <span style={{ opacity: 0.5 + highlightOpacity * 0.5, background: `rgba(34,197,94,${highlightOpacity * 0.2})`, borderRadius: 4, padding: "2px 0" }}>
              {trnPart}
            </span>
            <span
              style={{
                background: `rgba(34,197,94,${highlightOpacity * 0.3})`,
                borderRadius: 4,
                padding: "2px 6px",
                color: "#86efac",
                transform: `scale(${extractScale})`,
                display: "inline-block",
                boxShadow: extractGlow > 0.5 ? `0 0 20px rgba(34,197,94,${extractGlow * 0.4})` : "none",
              }}
            >
              {paymentNum}
            </span>
            <span style={{ opacity: 0.4 }}>{afterTrn}</span>
          </code>
        </div>
      </FadeIn>

      {/* Step 2: Extracted number */}
      <Sequence from={80} layout="none" premountFor={fps}>
        <FadeIn delay={80}>
          <div style={{ color: COLORS.lightGreen, fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Step 2: Look up EOB by payment_number
          </div>
          <div
            style={{
              background: "#1a2e28",
              borderRadius: 10,
              padding: "16px 28px",
              borderLeft: `4px solid ${COLORS.amber}`,
              marginBottom: 30,
              display: "flex",
              gap: 40,
            }}
          >
            <div>
              <div style={{ color: COLORS.textSecondary, fontSize: 13, fontFamily: "DM Sans, sans-serif", marginBottom: 4 }}>EOB.payment_number</div>
              <code style={{ fontFamily: monoFamily, fontSize: 22, color: "#86efac" }}>736886274</code>
            </div>
            <div>
              <div style={{ color: COLORS.textSecondary, fontSize: 13, fontFamily: "DM Sans, sans-serif", marginBottom: 4 }}>EOB.adjusted_amount</div>
              <code style={{ fontFamily: monoFamily, fontSize: 22, color: "#fcd34d" }}>$285.00</code>
            </div>
            <div>
              <div style={{ color: COLORS.textSecondary, fontSize: 13, fontFamily: "DM Sans, sans-serif", marginBottom: 4 }}>|bank_amount|</div>
              <code style={{ fontFamily: monoFamily, fontSize: 22, color: "#fcd34d" }}>$285.00</code>
            </div>
          </div>
        </FadeIn>
      </Sequence>

      {/* Step 3: Confidence */}
      <Sequence from={130} layout="none" premountFor={fps}>
        <FadeIn delay={130}>
          <div style={{ color: COLORS.lightGreen, fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
            Step 3: Confidence scoring
          </div>
          <div style={{ display: "flex", gap: 24 }}>
            <div
              style={{
                background: "rgba(34,197,94,0.12)",
                border: "1px solid rgba(34,197,94,0.3)",
                borderRadius: 10,
                padding: "14px 24px",
                textAlign: "center",
              }}
            >
              <div style={{ color: "#86efac", fontSize: 36, fontWeight: 700 }}>1.0</div>
              <div style={{ color: COLORS.textSecondary, fontSize: 14, marginTop: 4 }}>Exact amount match</div>
            </div>
            <div
              style={{
                background: "rgba(245,158,11,0.12)",
                border: "1px solid rgba(245,158,11,0.3)",
                borderRadius: 10,
                padding: "14px 24px",
                textAlign: "center",
              }}
            >
              <div style={{ color: "#fcd34d", fontSize: 36, fontWeight: 700 }}>0.9</div>
              <div style={{ color: COLORS.textSecondary, fontSize: 14, marginTop: 4 }}>Within $5 fee tolerance</div>
            </div>
            <div
              style={{
                background: "rgba(239,68,68,0.12)",
                border: "1px solid rgba(239,68,68,0.3)",
                borderRadius: 10,
                padding: "14px 24px",
                textAlign: "center",
              }}
            >
              <div style={{ color: "#fca5a5", fontSize: 36, fontWeight: 700 }}>Skip</div>
              <div style={{ color: COLORS.textSecondary, fontSize: 14, marginTop: 4 }}>Amount too far off</div>
            </div>
          </div>
        </FadeIn>
      </Sequence>

      <Caption
        text="~1,995 matches at 1.0 confidence. The TRN payment number is a direct clearinghouse reference -- the strongest signal in the dataset."
        startFrame={160}
      />
    </AbsoluteFill>
  );
};
