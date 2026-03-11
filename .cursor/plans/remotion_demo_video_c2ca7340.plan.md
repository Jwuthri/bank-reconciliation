---
name: Remotion Demo Video
overview: Create a Remotion video using screen recordings of the LIVE dashboard at localhost:8000 for UI scenes, plus animated graphics for architecture/pipeline explanations. Aimed at CTO, text-only narration (no voiceover).
todos:
  - id: capture-dashboard
    content: "Use browser automation (Playwright) to screen-record the live dashboard at http://127.0.0.1:8000: Overview page, Payments page (click a row to open match-detail modal), Inbox page (both tabs). Save as video clips in video/public/"
    status: completed
  - id: setup-remotion
    content: Initialize Remotion project in video/ with package.json, tsconfig, remotion.config, and install dependencies (remotion, @remotion/cli, @remotion/transitions, @remotion/google-fonts)
    status: completed
  - id: theme-components
    content: "Create theme.ts (brand colors/fonts) and shared components: Caption (bottom-third text overlay), AnimatedCounter, FlowNode, CodeBlock, BarChart"
    status: completed
  - id: scene-title
    content: Build TitleScene with spring-animated title and subtitle
    status: completed
  - id: scene-problem
    content: Build ProblemScene showing transaction volume, example bank notes, and noise vs signal
    status: completed
  - id: scene-pipeline
    content: Build PipelineScene with animated SVG flowchart of classify -> match pipeline
    status: completed
  - id: scene-payment-number
    content: Build PaymentNumberScene with TRN regex extraction animation and EOB lookup example
    status: completed
  - id: scene-payer-amount
    content: Build PayerAmountScene with MetLife matching example and confidence levels
    status: completed
  - id: scene-dashboard
    content: Build DashboardScene embedding the screen-recorded video clips of the real dashboard with text overlay captions explaining each view
    status: completed
  - id: scene-results
    content: Build ResultsScene with animated bar chart, key insights, future improvements, and closing card
    status: completed
  - id: compose-video
    content: Wire all scenes into Video.tsx with TransitionSeries + fade transitions, create Root.tsx composition, and render final mp4
    status: completed
isProject: false
---

# Remotion Demo Video for Lassie Bank Reconciliation

## Goal

Build a ~90-second Remotion video aimed at the CTO. Uses **screen recordings of the actual running dashboard** at `http://127.0.0.1:8000` for all UI walkthrough scenes, plus **animated Remotion graphics** for architecture/pipeline/matcher explanations. All narration via on-screen text/captions (no voiceover).

## Phase 1: Capture the Live Dashboard

Before building any Remotion code, record the real dashboard using Playwright browser automation. The dashboard is already running at `http://127.0.0.1:8000`.

### Recordings needed (saved to `video/public/`)

1. **overview.webm** -- Navigate to Overview page, pause to show stats cards and reconciliation stats, scroll down to "By Match Method" table
2. **payments.webm** -- Navigate to Payments page, scroll through rows, click a row to open the match-detail modal (showing EOB + bank transaction + confidence + method JSON), close modal
3. **inbox.webm** -- Navigate to Inbox, show Missing EOBs tab (with Link/Dismiss actions), switch to Missing Transactions tab

Each recording: 1920x1080 viewport, ~8-12 seconds, smooth mouse movements.

## Phase 2: Video Structure (7 scenes, ~90s at 30fps)

### Scene 1 -- Title Card (3s / 90 frames)

- Animated Remotion graphics
- "Lassie Bank Reconciliation Engine" with spring animation
- Subtitle: "Automated EOB-to-Transaction Matching for Dental Practices"

### Scene 2 -- The Problem (8s / 240 frames)

- Animated Remotion graphics
- "8,611 bank transactions. 3,526 EOBs. One messy bank account."
- Example bank notes fading in (structured, vague, noise)
- Caption: "The engine must separate signal from noise."

### Scene 3 -- Pipeline Architecture (12s / 360 frames)

- Animated SVG flowchart (Remotion graphics)
- Stage 1: Classification (rules-first, LLM fallback, precision mode)
- Stage 2: Sequential matching (PaymentNumber then PayerAmountDate)
- Caption: "Precision over recall -- false positives erode trust."

### Scene 4 -- PaymentNumberMatcher (10s / 300 frames)

- Animated Remotion graphics
- TRN regex extraction animation with highlight
- EOB lookup + amount verification
- Caption: "~1,995 matches at 1.0 confidence."

### Scene 5 -- PayerAmountDateMatcher (10s / 300 frames)

- Animated Remotion graphics
- MetLife example: payer + amount + date window
- Caption: "~844 matches. Ambiguous cases get lower confidence."

### Scene 6 -- Dashboard Walkthrough (25s / 750 frames)

- **Embedded screen recordings** of the real dashboard
- Sub-scene A (8s): Overview recording + caption "Classification and reconciliation KPIs at a glance"
- Sub-scene B (10s): Payments recording + caption "Click any row to inspect the full match chain -- EOB, bank transaction, confidence score, and match method"
- Sub-scene C (7s): Inbox recording + caption "Follow-up tasks: manually link or dismiss unresolved items"

### Scene 7 -- Results & Closing (12s / 360 frames)

- Animated bar chart (Remotion graphics): 93% EOB match rate, 54% txn match rate
- Key insight + future improvements
- Closing: "Lassie -- Reconciliation that earns trust."

## Technical Setup

### Remotion project at `video/`

```
video/
  package.json
  tsconfig.json
  remotion.config.ts
  public/
    overview.webm       # Screen recording from Playwright
    payments.webm       # Screen recording from Playwright
    inbox.webm          # Screen recording from Playwright
  src/
    Root.tsx
    index.ts
    Video.tsx            # TransitionSeries composing all scenes
    scenes/
      TitleScene.tsx
      ProblemScene.tsx
      PipelineScene.tsx
      PaymentNumberScene.tsx
      PayerAmountScene.tsx
      DashboardScene.tsx   # Embeds <Video> from public/*.webm
      ResultsScene.tsx
    components/
      Caption.tsx
      AnimatedCounter.tsx
      FlowNode.tsx
      CodeBlock.tsx
      BarChart.tsx
    styles/
      theme.ts
```

### Key Remotion Patterns

- All animations via `useCurrentFrame()` + `interpolate()` / `spring()` -- no CSS transitions
- `TransitionSeries` with `fade()` transitions between scenes (~15 frame crossfades)
- Google Fonts via `@remotion/google-fonts`: DM Sans (body) + JetBrains Mono (code)
- `<Sequence>` with `premountFor` for staggered reveals
- Screen recordings embedded via Remotion's `<Video>` component with `src={staticFile("overview.webm")}`
- Resolution: 1920x1080, 30fps

### Brand / Design

- Dashboard palette: `#1d4d3a`, `#2a643b`, `#22c55e`, `#ef4444`, `#f8faf9`
- Fonts: DM Sans + JetBrains Mono
- Caption style: bottom-third overlay, semi-transparent dark bg, white text, fade-in/out

### Rendering

```bash
cd video && npx remotion render src/index.ts BankReconciliation out/demo.mp4
```

