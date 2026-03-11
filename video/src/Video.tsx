import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";

import { TitleScene } from "./scenes/TitleScene";
import { ProblemScene } from "./scenes/ProblemScene";
import { PipelineScene } from "./scenes/PipelineScene";
import { PaymentNumberScene } from "./scenes/PaymentNumberScene";
import { PayerAmountScene } from "./scenes/PayerAmountScene";
import { DashboardScene } from "./scenes/DashboardScene";
import { ResultsScene } from "./scenes/ResultsScene";

const TRANSITION_FRAMES = 15;
const transition = (
  <TransitionSeries.Transition
    presentation={fade()}
    timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
  />
);

export const BankReconciliationVideo: React.FC = () => {
  return (
    <TransitionSeries>
      {/* Scene 1: Title (3s) */}
      <TransitionSeries.Sequence durationInFrames={90}>
        <TitleScene />
      </TransitionSeries.Sequence>
      {transition}

      {/* Scene 2: The Problem (8s) */}
      <TransitionSeries.Sequence durationInFrames={240}>
        <ProblemScene />
      </TransitionSeries.Sequence>
      {transition}

      {/* Scene 3: Pipeline Architecture (12s) */}
      <TransitionSeries.Sequence durationInFrames={360}>
        <PipelineScene />
      </TransitionSeries.Sequence>
      {transition}

      {/* Scene 4: PaymentNumberMatcher (10s) */}
      <TransitionSeries.Sequence durationInFrames={300}>
        <PaymentNumberScene />
      </TransitionSeries.Sequence>
      {transition}

      {/* Scene 5: PayerAmountDateMatcher (10s) */}
      <TransitionSeries.Sequence durationInFrames={300}>
        <PayerAmountScene />
      </TransitionSeries.Sequence>
      {transition}

      {/* Scene 6: Dashboard Walkthrough (25s) */}
      <TransitionSeries.Sequence durationInFrames={750}>
        <DashboardScene />
      </TransitionSeries.Sequence>
      {transition}

      {/* Scene 7: Results & Closing (12s) */}
      <TransitionSeries.Sequence durationInFrames={360}>
        <ResultsScene />
      </TransitionSeries.Sequence>
    </TransitionSeries>
  );
};
