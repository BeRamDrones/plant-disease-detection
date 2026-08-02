"use client";
import React, { useState, useCallback } from "react";
import MissionHeader from "@/components/MissionHeader";
import CameraFeed from "@/components/CameraFeed";
import DetectionPanel from "@/components/DetectionPanel";
import ZoneMap from "@/components/ZoneMap";
import StatsBar from "@/components/StatsBar";
import CompleteMissionButton from "@/components/CompleteMissionButton";
import ModelGate from "@/components/ModelGate";
import InputModeSelector, { InputMode } from "@/components/InputModeSelector";
import { useMissionDetections } from "@/hooks/useMissionDetections";
import { useModelStatus } from "@/hooks/useModelStatus";
import { useDetections, RawDetection } from "@/hooks/useDetections";
import { generateMissionSummary } from "@/lib/mockData";
import {
  RotateCcw,
  LayoutDashboard, Radio, Map, BarChart2, Settings,
} from "lucide-react";
import styles from "./page.module.css";

// ── Simulated drone telemetry with subtle drift ───────────────────────────────
function useTelemetry() {
  const [alt,   setAlt]   = React.useState(85.4);
  const [speed, setSpeed] = React.useState(12.3);
  const [bat,   setBat]   = React.useState(78);
  const [sig,   setSig]   = React.useState(92);
  const [lat,   setLat]   = React.useState(21.1455);
  const [lon,   setLon]   = React.useState(79.0882);

  React.useEffect(() => {
    const t = setInterval(() => {
      setAlt  (v => +(v + (Math.random()-0.5)*0.3).toFixed(1));
      setSpeed(v => +(v + (Math.random()-0.5)*0.4).toFixed(1));
      setBat  (v => Math.max(5, +(v - 0.015).toFixed(1)));
      setSig  (v => Math.min(100, Math.max(60, v + (Math.random()-0.5)*2)));
      setLat  (v => +(v + (Math.random()-0.5)*0.0001).toFixed(5));
      setLon  (v => +(v + (Math.random()-0.5)*0.0001).toFixed(5));
    }, 1500);
    return () => clearInterval(t);
  }, []);

  return { alt, speed, bat, sig, lat, lon };
}

// ── Nav items ─────────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: "dashboard", icon: <LayoutDashboard size={18} />, label: "DASH"   },
  { id: "stream",    icon: <Radio size={18} />,           label: "STREAM" },
  { id: "map",       icon: <Map size={18} />,             label: "MAP"    },
  { id: "analytics", icon: <BarChart2 size={18} />,       label: "DATA"   },
  { id: "settings",  icon: <Settings size={18} />,        label: "CFG"    },
] as const;

// ─────────────────────────────────────────────────────────────────────────────
export default function MissionDashboard() {
  const modelStatus = useModelStatus();
  const { mission, elapsed } = useMissionDetections();
  const { detections, addDetections, clearDetections, totalScans } = useDetections();
  const { alt, speed, bat, sig, lat, lon } = useTelemetry();
  const summary = generateMissionSummary(detections, mission);

  const [activeNav, setActiveNav] = useState<string>("dashboard");
  const [inputMode, setInputMode] = useState<InputMode>("live");

  /**
   * Called by CameraFeed whenever the backend returns real detections.
   * Passes current drone GPS so detections are pinned to the right location.
   */
  const handleDetections = useCallback((raws: RawDetection[]) => {
    addDetections(raws, lat, lon);
  }, [addDetections, lat, lon]);

  return (
    <div className={styles.root}>
      {/* ── Model gate overlay ── */}
      <ModelGate status={modelStatus} />

      {/* ── Top nav ── */}
      <MissionHeader
        mission={mission}
        elapsed={elapsed}
        signalStrength={Math.round(sig)}
        battery={Math.round(bat)}
        modelStatus={modelStatus}
      />

      {/* ── Main layout ── */}
      <div className={styles.body}>

        {/* LEFT: vertical nav sidebar */}
        <nav className={styles.sidebar}>
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`${styles.navBtn} ${activeNav === item.id ? styles.navActive : ""}`}
              onClick={() => setActiveNav(item.id)}
              title={item.label}
            >
              {item.icon}
              <span className={styles.navLabel}>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* CENTER: Camera feed + controls */}
        <div className={styles.mainCol}>
          {/* Mode selector strip */}
          <div className={styles.modeStrip}>
            <InputModeSelector
              mode={inputMode}
              onModeChange={mode => { setInputMode(mode); clearDetections(); }}
              modelReady={modelStatus.ready}
            />

            {/* Stats + clear */}
            <div className={styles.ctrlGroup}>
              {/* Running tally chips */}
              <div className={styles.detChips}>
                <span className={styles.chip} style={{ color:"#22c55e", borderColor:"rgba(34,197,94,0.3)", background:"rgba(34,197,94,0.08)" }}>
                  {detections.filter(d => d.detected_class === "healthy").length} HEALTHY
                </span>
                <span className={styles.chip} style={{ color:"#ef4444", borderColor:"rgba(239,68,68,0.3)", background:"rgba(239,68,68,0.08)" }}>
                  {detections.filter(d => d.detected_class !== "healthy").length} DISEASED
                </span>
                {totalScans > 0 && (
                  <span className={styles.chip} style={{ color:"#a855f7", borderColor:"rgba(168,85,247,0.3)", background:"rgba(168,85,247,0.08)" }}>
                    {totalScans} SCANS
                  </span>
                )}
              </div>
              <div className={styles.ctrlDivider}/>
              <button
                className={styles.ctrlBtn}
                onClick={clearDetections}
                title="Clear all detections"
                disabled={!modelStatus.ready || detections.length === 0}
              >
                <RotateCcw size={11}/>
                <span>CLEAR</span>
              </button>
            </div>
          </div>

          {/* Camera feed — onDetections wired to real inference results only */}
          <div className={styles.feedWrap}>
            <CameraFeed
              altitude={alt}
              speed={speed}
              lat={lat}
              lon={lon}
              mode={inputMode}
              modelReady={modelStatus.ready}
              onDetections={handleDetections}
            />
          </div>
        </div>

        {/* RIGHT panel A: Detection feed — only real model results */}
        <div className={styles.detectCol}>
          <DetectionPanel
            detections={detections}
            modelReady={modelStatus.ready}
            totalScans={totalScans}
          />
        </div>

        {/* RIGHT panel B: Zone map + health + zone list + CTA */}
        <div className={styles.rightCol}>
          <ZoneMap zones={summary.zones_breakdown}/>

          {/* Health gauge */}
          <div className={styles.healthCard}>
            <div className={styles.healthHeader}>
              <span className={styles.healthLabel}>MISSION HEALTH SCORE</span>
              <span className={styles.healthPct} style={{
                color: summary.health_score >= 70 ? "#22c55e" : summary.health_score >= 40 ? "#f59e0b" : "#ef4444"
              }}>
                {summary.health_score.toFixed(1)}%
              </span>
            </div>
            <div className={styles.healthBar}>
              <div className={styles.healthFill} style={{
                width: `${summary.health_score}%`,
                background: summary.health_score >= 70 ? "#22c55e" : summary.health_score >= 40 ? "#f59e0b" : "#ef4444",
              }}/>
              <div className={styles.healthShimmer}/>
            </div>
          </div>

          {/* Zone breakdown list */}
          <div className={styles.zoneList}>
            <div className={styles.zoneListHeader}>ZONE STATUS</div>
            <div className={styles.zoneItems}>
              {summary.zones_breakdown
                .filter(z => z.detection_count > 0)
                .sort((a,b) => b.detection_count - a.detection_count)
                .slice(0,6)
                .map(z => (
                  <div key={z.zone_id} className={styles.zoneItem}>
                    <span className={styles.zoneItemLabel}>{z.zone_label}</span>
                    <span className={styles.zoneItemClass}>
                      {(z.dominant_class ?? "—").replace(/_/g," ").toUpperCase()}
                    </span>
                    <span className={styles.zoneItemCount}>{z.detection_count}</span>
                  </div>
                ))}
              {summary.zones_breakdown.filter(z => z.detection_count > 0).length === 0 && (
                <div className={styles.noZones}>No detections yet — submit an image or start live scan</div>
              )}
            </div>
          </div>

          <CompleteMissionButton mission={mission} detections={detections} elapsed={elapsed}/>
        </div>
      </div>

      {/* ── Bottom stats bar ── */}
      <StatsBar
        detections={detections}
        zones={summary.zones_breakdown}
        healthScore={summary.health_score}
        inputMode={inputMode}
        modelStatus={modelStatus}
      />
    </div>
  );
}
