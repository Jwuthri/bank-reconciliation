import React from "react";
import { Composition } from "remotion";
import { BankReconciliationVideo } from "./Video";
import { FPS, WIDTH, HEIGHT } from "./styles/theme";

// 7 scenes: 90 + 240 + 360 + 300 + 300 + 750 + 360 = 2400
// Minus 6 transitions of 15 frames each = -90
// Total: 2310 frames = 77 seconds at 30fps
const TOTAL_FRAMES = 2310;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="BankReconciliation"
      component={BankReconciliationVideo}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  );
};
