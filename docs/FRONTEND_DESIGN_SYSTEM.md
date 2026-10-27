# SentinelLLM — Frontend Design System & SecOps Visual Language

> **Document Status:** Authoritative Design Specification (Milestone 4)  
> **Framework:** Next.js 15 (App Router), React 19, Tailwind CSS  
> **Design Philosophy:** Developer-Security & SecOps Operations Console

---

## 1. Visual Philosophy: Restrained, Purposeful, Dense

SentinelLLM is an adversarial evaluation platform and runtime security gateway for AI workloads. The interface must communicate authority, precision, and operational clarity.

### Anti-Patterns Strictly Avoided
* **No Marketing Fluff:** No oversized purple-to-cyan radial gradients, floating amorphous blobs, or marketing hero copy.
* **No Over-Rounded Toy Cards:** Avoid oversized `rounded-3xl` bubble containers; use crisp, structured `rounded-md` or `rounded-lg` with disciplined 1px borders.
* **No Meaningless Vanity Metrics:** Every displayed number links directly to real telemetry (`readiness`, `audit_events`, `approval_requests`, or `benchmark_runs`).
* **No Fake Activity:** Real empty states (`No pending approval requests in queue`) replace fabricated ticker charts.

---

## 2. Color Palette & Contrast Architecture

The palette uses a high-contrast dark theme optimized for SecOps monitoring and long analytical sessions:

| Token | Hex Value | Semantic Usage |
| :--- | :--- | :--- |
| `background` | `#080c14` | Deep obsidian canvas; reduces eye fatigue |
| `card` | `#0e1422` | Surface level 1; elevated panels with sharp borders |
| `card-muted` | `#0b101c` | Surface level 0; code viewports, table headers, inset wells |
| `border` | `#1e293b` | 1px boundary lines (`slate-800`) |
| `border-subtle` | `#141f32` | Secondary dividers |
| `foreground` | `#f1f5f9` | Primary headings, values, and high-emphasis text (`slate-100`) |
| `text-muted` | `#94a3b8` | Secondary labels, descriptions, and metadata (`slate-400`) |
| `text-subtle` | `#64748b` | Tertiary timestamps and inactive navigation (`slate-500`) |

### Semantic Status Tokens
* **Security Block / Violation:** `#ef4444` (`red-500`) | Background: `rgba(239, 68, 68, 0.1)` | Border: `rgba(239, 68, 68, 0.25)`
* **Human-in-the-Loop Review:** `#f59e0b` (`amber-500`) | Background: `rgba(245, 158, 11, 0.1)` | Border: `rgba(245, 158, 11, 0.25)`
* **Policy Allow / Safe Pass:** `#10b981` (`emerald-500`) | Background: `rgba(16, 185, 129, 0.1)` | Border: `rgba(16, 185, 129, 0.25)`
* **System Telemetry / Info:** `#38bdf8` (`sky-400`) | Accent: `#6366f1` (`indigo-500`)

---

## 3. Typography & Information Hierarchy

* **Primary Sans-Serif:** `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, `Inter`, `Roboto`, sans-serif.
* **Data & Telemetry Monospace:** `JetBrains Mono`, `ui-monospace`, `SFMono-Regular`, `Menlo`, monospace.
* **Hierarchy:**
  * **Section Headings:** `text-lg font-semibold tracking-tight text-slate-100`
  * **Card Titles:** `text-xs font-semibold uppercase tracking-wider text-slate-400`
  * **Metric Callouts:** `text-2xl font-bold font-mono tracking-tight text-slate-100`
  * **Table Cells:** `text-xs font-mono text-slate-300`
  * **Status Pills:** `text-[11px] font-mono font-medium px-2 py-0.5 rounded`

---

## 4. Layout Structure & Responsive Grids

* **Left Sidebar Navigation (Fixed 240px Desktop, Drawer on Mobile):**
  - Gateway Identity & Version Tag (`v1.0.0-rc.1`)
  - Operational Routes:
    - Overview (System Health, Activity, Quick Actions)
    - Interactive Playground (Gateway Ingestion & Inspection)
    - Approval Queue (Pending, Approved, Rejected, Consumed)
    - Audit Explorer (Structured Telemetry & Filters)
    - Threat Benchmark (PromptProbe Adversarial Suite)
    - Policy & Tools (Registered Tools & Execution Rules)
    - Security Walkthrough (6-Stage Deterministic Demo)
  - Active Persona Display with Role Badge
* **Top Bar (Sticky 56px):**
  - Active Persona Selector (`Sec Admin`, `Supervisor`, `Analyst`, `Guest`)
  - Backend Gateway Connectivity Indicator (Green/Red Pulse)
  - Quick Documentation & GitHub Links
* **Main Viewport:**
  - Max width constrained with flexible responsive columns (1-col mobile, 2-col tablet, 3-col or 4-col desktop).
  - Dense, readable data tables with horizontal scroll containers.

---

## 5. Interaction Details & States

1. **Loading State:** Subtle pulse skeleton wells matching exact card geometry; no jarring layout shifts.
2. **Empty State:** Purposeful empty state illustration or iconography with clear diagnostic copy and direct call-to-action buttons.
3. **Error State:** Explicit error alerts explaining the exact cause (e.g. backend connectivity failure, 401 unauthenticated, 403 permission denied) with immediate retry buttons.
4. **Interactive Badges:** Hover state on status badges with tooltips explaining policy decision codes (`DENY_HIGH_RISK_FINDINGS`, `REVIEW_APPROVAL_REQUIRED`).
