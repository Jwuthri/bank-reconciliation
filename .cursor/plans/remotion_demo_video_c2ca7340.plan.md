---
name: Remotion Demo Video
overview: Create a Remotion video project showcasing the Lassie Bank Reconciliation engine for the CTO -- covering architecture, matching techniques, dashboard walkthrough, and results -- using on-screen text/captions instead of voiceover.
todos:
  - id: setup-remotion
    content: Initialize Remotion project in video/ with package.json, tsconfig, remotion.config, and install dependencies (remotion, @remotion/cli, @remotion/transitions, @remotion/google-fonts)
    status: pending
  - id: theme-components
    content: "Create theme.ts (brand colors/fonts) and shared components: Caption, AnimatedCounter, StatCard, CodeBlock, BarChart, StatusBadge, FlowNode"
    status: pending
  - id: scene-title
    content: Build TitleScene with spring-animated title and subtitle
    status: pending
  - id: scene-problem
    content: Build ProblemScene showing transaction volume, example bank notes, and noise vs signal
    status: pending
  - id: scene-pipeline
    content: Build PipelineScene with animated SVG flowchart of classify -> match pipeline
    status: pending
  - id: scene-payment-number
    content: Build PaymentNumberScene with TRN regex extraction animation and EOB lookup example
    status: pending
  - id: scene-payer-amount
    content: Build PayerAmountScene with MetLife matching example and confidence levels
    status: pending
  - id: scene-dashboard
    content: Build DashboardScene showing Overview stats, Payments table with click-to-inspect, and Inbox tabs
    status: pending
  - id: scene-results
    content: Build ResultsScene with animated bar chart, key insights, future improvements, and closing card
    status: pending
  - id: compose-video
    content: Wire all scenes into Video.tsx with TransitionSeries + fade transitions, create Root.tsx composition, and verify rendering
    status: pending
isProject: false
---

# Remotion Demo Video for Lassie Bank Reconciliation

## Goal

Build a ~90-second Remotion video aimed at the CTO that demonstrates the reconciliation engine: what it does, the technical approach (classification + matching pipeline), the dashboard UI, and the results. All narration via on-screen text/captions (no voiceover).

## Video Structure (7 scenes, ~90s at 30fps = ~2700 frames)

### Scene 1 -- Title Card (3s / 90 frames)

- "Lassie Bank Reconciliation Engine" title with spring animation
- Subtitle: "Automated EOB-to-Transaction Matching for Dental Practices"
- Clean dark-green brand palette matching the dashboard (#1d4d3a, #2a643b)

### Scene 2 -- The Problem (8s / 240 frames)

- Text: "8,611 bank transactions. 3,526 EOBs. One messy bank account."
- Animated counter showing transaction volume
- Show example bank notes fading in:
  - `"HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*..."` (useful)
  - `"MetLife"` (vague)
  - `"PAYROLL"` / `"rent"` / `"Porsche payment"` (noise)
- Caption: "Transaction notes range from structured clearinghouse data to completely unrelated business expenses. The engine must separate signal from noise."

### Scene 3 -- Two-Stage Pipeline Architecture (12s / 360 frames)

- Animated flowchart (built with React/SVG, not mermaid):
  1. **Stage 1: Classification** -- Rules-first, LLM fallback
    - Insurance rules: HCCLAIMPMT, MetLife, Guardian, CALIFORNIA DENTA
    - Noise rules: payroll, rent, card settlement, fees (~30 patterns)
    - Unknown -> precision mode (default NOT insurance) or LLM (gpt-5-mini)
  2. **Stage 2: Sequential Matching** -- High-confidence first
    - PaymentNumberMatcher: TRN extraction, EOB lookup, confidence 1.0/0.9
    - PayerAmountDateMatcher: payer + amount + 14-day window, confidence 0.85/0.7
- Caption: "Precision over recall -- false positives erode trust. Better to under-flag than tell a practice their payroll is a missing insurance payment."

### Scene 4 -- PaymentNumberMatcher Deep Dive (10s / 300 frames)

- Animated example:
  - Bank note: `"HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\"`
  - Regex extraction animation: highlight `TRN*1`* then extract `736886274`
  - Arrow to EOB table: `payment_number = "736886274"`, `adjusted_amount = $285.00`
  - Amount check: `|bank_amount| == adjusted_amount` -> confidence 1.0
  - Fee tolerance: within 500c ($5) -> confidence 0.9
- Caption: "~1,995 matches at 1.0 confidence. The TRN payment number is a direct clearinghouse reference -- the strongest signal in the dataset."

### Scene 5 -- PayerAmountDateMatcher Deep Dive (10s / 300 frames)

- Animated example:
  - Bank note: `"MetLife"` | Amount: $241.20 | Date: Sep 9
  - Payer identification (case-insensitive note matching)
  - EOB lookup: payer=MetLife, adjusted_amount=$241.20, date within +/-14 days
  - Single candidate -> confidence 0.85
  - Multiple candidates -> closest date wins, confidence 0.7
- Caption: "~844 matches. No reference number -- we rely on payer + amount + date window. Ambiguous cases get lower confidence for manual review."

### Scene 6 -- Dashboard Walkthrough (25s / 750 frames)

- **Overview page**: Animated stat cards counting up
  - 8,611 total transactions | 5,238 insurance | 3,373 not insurance | 0 unknown
  - 3,526 EOBs | 2,839 matched | 233 unmatched EOBs | 2,399 unmatched txns
  - Match methods: payment_number (1,995) | payer_amount_date (844)
- **Payments page**: Table with rows showing date, payer, payment #, amount, method, TXN/EOB status badges (RECEIVED/AWAITING)
  - Highlight: "Click any row to inspect the match" -> modal opens showing JSON with EOB data, bank transaction data, match confidence and method
- **Inbox page**: Missing EOBs tab and Missing Transactions tab
  - Manual reconcile: enter ID + Link button
  - Dismiss: remove false positives
- Caption: "Three views: Overview for KPIs, Payments for the reconciled ledger, Inbox for follow-up tasks. Click-to-inspect reveals the full match chain."

### Scene 7 -- Results and Closing (12s / 360 frames)

- Animated bar chart:
  - EOB match rate: 93% (3,293 of 3,526)
  - Insurance txn match rate: 54% (2,839 of 5,238)
- Key insight text: "Main gap: 1,677 TRN payment numbers exist in bank notes but not in EOB data -- a data alignment issue, not a code issue."
- Future improvements list (fade in):
  - Constraint relaxation (date window, amount tolerance)
  - HCCLAIMPMT payer code mapping
  - Adaptive payer-specific date windows
  - Scheduled reconciliation + audit trail
- Final card: "Lassie -- Reconciliation that earns trust."

## Technical Setup

### New Remotion project inside the repo

Create a `video/` directory at the project root with:

```
video/
  package.json          # remotion + @remotion/cli + @remotion/transitions + @remotion/google-fonts
  tsconfig.json
  remotion.config.ts
  src/
    Root.tsx             # Composition definition (~2700 frames, 30fps, 1920x1080)
    index.ts             # registerRoot
    Video.tsx            # Main composition using TransitionSeries
    scenes/
      TitleScene.tsx
      ProblemScene.tsx
      PipelineScene.tsx
      PaymentNumberScene.tsx
      PayerAmountScene.tsx
      DashboardScene.tsx
      ResultsScene.tsx
    components/
      AnimatedCounter.tsx
      Caption.tsx         # Bottom-third text overlay with fade-in
      StatCard.tsx
      FlowNode.tsx        # Pipeline diagram node
      CodeBlock.tsx       # Syntax-highlighted code/note display
      BarChart.tsx
      StatusBadge.tsx
    styles/
      theme.ts            # Brand colors, font config
```

### Key Remotion Patterns (from skill rules)

- All animations via `useCurrentFrame()` + `interpolate()` / `spring()` -- no CSS transitions
- `TransitionSeries` with `fade()` transitions between scenes (~15 frame crossfades)
- Google Fonts: `@remotion/google-fonts` for DM Sans (body) + JetBrains Mono (code)
- `<Sequence>` with `premountFor` for staggered element reveals
- Spring configs: `{ damping: 200 }` for smooth reveals, `{ damping: 20, stiffness: 200 }` for snappy UI elements
- Charts: SVG bar charts driven by `spring()` with stagger delay
- Resolution: 1920x1080 (16:9), 30fps

### Brand / Design

- Colors from the dashboard: `#1d4d3a` (dark green), `#2a643b` (primary green), `#22c55e` (success), `#ef4444` (awaiting/error), `#f8faf9` (background)
- Fonts: DM Sans (matches dashboard), JetBrains Mono for code/data
- Caption style: bottom-third overlay, semi-transparent dark background, white text, fade-in/out

### Rendering

After building, render with:

```bash
cd video && npx remotion render src/index.ts BankReconciliation out/demo.mp4
```

## Data to Hardcode in Video

All stats from the real pipeline output (no live DB queries in the video):


| Metric                   | Value       |
| ------------------------ | ----------- |
| Total transactions       | 8,611       |
| Insurance                | 5,238       |
| Not insurance            | 3,373       |
| Unknown                  | 0           |
| Total EOBs               | 3,526       |
| Matched EOBs             | 3,293 (93%) |
| Matched insurance txns   | 2,839 (54%) |
| PaymentNumber matches    | 1,995       |
| PayerAmountDate matches  | 844         |
| Unmatched EOBs           | 233         |
| Unmatched insurance txns | 2,399       |


