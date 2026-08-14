# 🎨 Project Jatayu — UI Color Theme

**Style:** Enterprise Mission Control / UAV Ops Dashboard — dark, cinematic, tactical-tech aesthetic (think radar consoles + Awwwards dark-mode SaaS)

Base palette derived from your reference swatch (steel-navy fabric tones) + extracted directly from the Jatayu dashboard screenshots (DASH, STREAM, MAP, DATA, CFG panels).

---

## 1. Base Palette (Steel Navy — from reference swatch)

| Token | Hex | Preview | Usage |
|---|---|---|---|
| `navy-950` | `#1C2839` | 🟦 | Deepest shadows, sidebar background, card edges |
| `navy-800` | `#2D3D52` | 🟦 | Primary panel background, card fill |
| `navy-600` | `#415169` | 🟦 | Secondary panel fill, hover states, dividers |
| `navy-400` | `#5E6D88` | 🟦 | Muted text, disabled states, placeholder icons |

---

## 2. Extended Backgrounds (from dashboard screenshots)

The actual app runs **darker** than the base swatch — it uses near-black navy as the canvas, with the swatch tones layered on top for cards/panels.

| Token | Hex | Usage |
|---|---|---|
| `bg-canvas` | `#0A0E16` | Root app background (behind everything) |
| `bg-surface` | `#0D1420` | Main content panel background |
| `bg-panel` | `#111927` | Cards, side panels, table containers |
| `bg-panel-alt` | `#141D2B` | Nested/inset panels (e.g. "no camera" box, console log box) |
| `bg-sidebar` | `#0B1119` | Left nav rail background |
| `border-subtle` | `#1E2A3A` | Card borders, table row dividers |
| `border-strong` | `#2D3D52` | Active tab border, focused input border |

---

## 3. Accent — Cyan/Teal (Primary Brand Accent)

This is the signature "HUD glow" color used across nav icons, active states, headings, buttons, and data readouts.

| Token | Hex | Usage |
|---|---|---|
| `accent-primary` | `#22D3EE` | Primary buttons, active nav tab, highlighted values (GPS, timers) |
| `accent-primary-bright` | `#5EEAF7` | Glow/hover state, logo icon |
| `accent-primary-muted` | `#0E7490` | Secondary icons, inactive-but-visible UI |
| `accent-primary-dim` | `#0B2530` | Active tab background wash, badge backgrounds |

**Used for:** logo mark, "PROJECT JATAYU" title, active sidebar item (DASH/STREAM/MAP/DATA/CFG), tab underline, primary CTA button ("COMPLETE MISSION" outline), links, slider handles, GPS/timestamp values, table headers.

---

## 4. Semantic / Status Colors

These are the colors your frontend **needs but wasn't fully using yet** — required for alerts, health scores, live status, and form validation across the whole app.

### 🟢 Success / Green
| Token | Hex | Usage |
|---|---|---|
| `success-500` | `#22C55E` | Live status dot ("● BEST.PT"), "READY" badge, healthy crop tag |
| `success-400` | `#4ADE80` | Hover/bright variant, success toast |
| `success-100` | `#0F2E1D` | Success badge background (dark wash) |
| `success-text` | `#86EFAC` | Text inside success badges on dark bg |

**Use for:** model-online indicator, "IN_PROGRESS" positive state, health score bar (when >70%), success toasts, "connected" states, healthy-leaf classification tags.

### 🔴 Error / Red — Danger, Alerts
| Token | Hex | Usage |
|---|---|---|
| `danger-500` | `#EF4444` | "DISEASED ALERTS" counter, no-camera icon, destructive buttons |
| `danger-400` | `#F87171` | Hover state on danger buttons |
| `danger-100` | `#2C1416` | Danger badge background (dark wash) |
| `danger-text` | `#FCA5A5` | Error message text on dark bg |

**Use for:** disease-detected alerts, camera-off icon, delete/clear actions, validation errors, critical health-score state (<40%), stop/abort mission button.

### 🟠 Warning / Amber
| Token | Hex | Usage |
|---|---|---|
| `warning-500` | `#F59E0B` | Warning triangle icon (⚠ Diseased Alerts label icon), caution banners |
| `warning-400` | `#FBBF24` | Hover / bright accent |
| `warning-100` | `#2A1D0A` | Warning badge background |

**Use for:** mid-range health score (40–70%), "low confidence" detections, pending/standby states (e.g. "CHILD MODELS: STANDBY"), zone-discovery-active badge alt state.

### 🔵 Info / Blue (distinct from primary cyan — for neutral info states)
| Token | Hex | Usage |
|---|---|---|
| `info-500` | `#3B82F6` | Informational badges, "DISCOVERY ACTIVE" pill |
| `info-100` | `#0E1B33` | Info badge background |

---

## 5. Text Colors

| Token | Hex | Usage |
|---|---|---|
| `text-primary` | `#E8EEF5` | Headings, primary readouts, table cell text |
| `text-secondary` | `#8FA0B8` | Labels (e.g. "MISSION", "STATUS"), sub-text |
| `text-muted` | `#5E6D88` | Placeholder text, empty-state copy, timestamps (secondary) |
| `text-disabled` | `#3B4758` | Disabled buttons/tabs (e.g. greyed "CLEAR" button) |
| `text-on-accent` | `#0A0E16` | Text placed on top of bright cyan buttons |

---

## 6. Component-Specific Mapping (from screenshots)

| Element | Color Token |
|---|---|
| Logo triangle icon | `accent-primary` |
| Sidebar active item bg | `accent-primary-dim` + left border `accent-primary` |
| "IN_PROGRESS" status text | `accent-primary-bright` |
| Neural Model live dot | `success-500` |
| "0 CROPS CLASSIFIED" pill | `bg-panel-alt` border `border-subtle` |
| "CHILD MODELS: STANDBY" pill | `warning-100` bg / `warning-400` text |
| "DISCOVERY ACTIVE" badge | `info-500` bg / `#FFFFFF` text |
| No-camera icon + text | `accent-primary-muted` (teal-grey, not red — it's a neutral empty state) |
| "STREAM OFFLINE" dot | `text-muted` |
| Mission Health Score % | `success-500` (100%) → shifts to `warning-500` / `danger-500` as it drops |
| Health score progress bar track | `bg-panel-alt`; fill = success/warning/danger by value |
| "COMPLETE MISSION" button | fill `accent-primary`, text `text-on-accent` |
| Bottom stat bar — "TOTAL DETECTIONS" value | `accent-primary` |
| Bottom stat bar — "DISEASED ALERTS" value + icon | `danger-500` |
| Bottom stat bar — "ZONES ACTIVE" | `text-primary` |
| Bottom stat bar — "HEALTH SCORE" shield icon | `success-500` |
| Table header row (DATA tab) | `text-secondary` on `bg-panel` |
| Table empty state text | `text-muted` |
| CFG sliders (Confidence Threshold, Scan Rate) | track `border-subtle`, filled portion `accent-primary`, handle `accent-primary-bright` with glow |
| Hardware console log box | `bg-panel-alt` bg, text `accent-primary-muted`, prefixed tags (`[SYS]`, `[YOLO]`) in `text-secondary` |
| GPU temp/VRAM readout | `accent-primary` |

---

## 7. CSS Variables (drop-in)

```css
:root {
  /* Base navy */
  --navy-950: #1C2839;
  --navy-800: #2D3D52;
  --navy-600: #415169;
  --navy-400: #5E6D88;

  /* Backgrounds */
  --bg-canvas: #0A0E16;
  --bg-surface: #0D1420;
  --bg-panel: #111927;
  --bg-panel-alt: #141D2B;
  --bg-sidebar: #0B1119;
  --border-subtle: #1E2A3A;
  --border-strong: #2D3D52;

  /* Accent (cyan/teal) */
  --accent-primary: #22D3EE;
  --accent-primary-bright: #5EEAF7;
  --accent-primary-muted: #0E7490;
  --accent-primary-dim: #0B2530;

  /* Success */
  --success-500: #22C55E;
  --success-400: #4ADE80;
  --success-100: #0F2E1D;
  --success-text: #86EFAC;

  /* Danger */
  --danger-500: #EF4444;
  --danger-400: #F87171;
  --danger-100: #2C1416;
  --danger-text: #FCA5A5;

  /* Warning */
  --warning-500: #F59E0B;
  --warning-400: #FBBF24;
  --warning-100: #2A1D0A;

  /* Info */
  --info-500: #3B82F6;
  --info-100: #0E1B33;

  /* Text */
  --text-primary: #E8EEF5;
  --text-secondary: #8FA0B8;
  --text-muted: #5E6D88;
  --text-disabled: #3B4758;
  --text-on-accent: #0A0E16;
}
```

---

## 8. Tailwind Config Extension

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#1C2839',
          800: '#2D3D52',
          600: '#415169',
          400: '#5E6D88',
        },
        canvas: '#0A0E16',
        surface: '#0D1420',
        panel: {
          DEFAULT: '#111927',
          alt: '#141D2B',
        },
        sidebar: '#0B1119',
        border: {
          subtle: '#1E2A3A',
          strong: '#2D3D52',
        },
        accent: {
          DEFAULT: '#22D3EE',
          bright: '#5EEAF7',
          muted: '#0E7490',
          dim: '#0B2530',
        },
        success: {
          DEFAULT: '#22C55E',
          400: '#4ADE80',
          100: '#0F2E1D',
          text: '#86EFAC',
        },
        danger: {
          DEFAULT: '#EF4444',
          400: '#F87171',
          100: '#2C1416',
          text: '#FCA5A5',
        },
        warning: {
          DEFAULT: '#F59E0B',
          400: '#FBBF24',
          100: '#2A1D0A',
        },
        info: {
          DEFAULT: '#3B82F6',
          100: '#0E1B33',
        },
        text: {
          primary: '#E8EEF5',
          secondary: '#8FA0B8',
          muted: '#5E6D88',
          disabled: '#3B4758',
          onAccent: '#0A0E16',
        },
      },
      boxShadow: {
        'glow-accent': '0 0 12px rgba(34, 211, 238, 0.45)',
        'glow-success': '0 0 10px rgba(34, 197, 94, 0.4)',
        'glow-danger': '0 0 10px rgba(239, 68, 68, 0.4)',
      },
    },
  },
};
```

---

## 9. Usage Rules (keep the tactical-HUD feel consistent)

1. **Only one bright accent** at a time per component — cyan is the hero color; don't let green/red compete with it for visual weight unless they're status-critical.
2. **Green/Red/Amber are reserved for status only** — never use them decoratively. Green = healthy/online/success. Red = disease detected/offline-critical/destructive. Amber = pending/caution/mid-range score.
3. **Glows over gradients** — use `box-shadow` glow (see `boxShadow` tokens above) on active/live elements (dots, sliders, buttons) instead of gradients, to match the HUD/radar look in the screenshots.
4. **Badges always get a dark tinted background** (`*-100` tokens) with bright text on top (`*-text` / `*-400`) — never solid bright fills except on primary CTA buttons.
5. **Borders stay subtle** — `border-subtle` (#1E2A3A) is the default; only active/focused elements get `border-strong` or `accent-primary`.
6. Health-score-driven UI (progress bars, badges) should **interpolate**: `success` (≥70%) → `warning` (40–69%) → `danger` (<40%).

---

*Extracted from Project Jatayu UAV Mission Control screenshots + base steel-navy reference swatch. Ready to drop into `globals.css` / `tailwind.config.js`.*
