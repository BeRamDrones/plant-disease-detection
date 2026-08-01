"use client";
import React, { useRef, useState, useEffect } from "react";
import MissionHeader from "@/components/MissionHeader";
import CameraFeed from "@/components/CameraFeed";
import DetectionPanel from "@/components/DetectionPanel";
import ZoneMap from "@/components/ZoneMap";
import StatsBar from "@/components/StatsBar";
import CompleteMissionButton from "@/components/CompleteMissionButton";
import { useMissionDetections } from "@/hooks/useMissionDetections";
import { generateMissionSummary } from "@/lib/mockData";
import { Pause, Play, RotateCcw } from "lucide-react";
import styles from "./page.module.css";

// Simulated drone telemetry values with subtle drift
function useTelemetry() {
  const [alt, setAlt]     = useState(85.4);
  const [speed, setSpeed] = useState(12.3);
  const [bat, setBat]     = useState(78);
  const [sig, setSig]     = useState(92);
  const [lat, setLat]     = useState(21.1455);
  const [lon, setLon]     = useState(79.0882);

  useEffect(() => {
    const t = setInterval(() => {
      setAlt(v  => +(v + (Math.random()-0.5)*0.3).toFixed(1));
      setSpeed(v=> +(v + (Math.random()-0.5)*0.4).toFixed(1));
      setBat(v  => Math.max(5, +(v - 0.015).toFixed(1)));
      setSig(v  => Math.min(100, Math.max(60, v + (Math.random()-0.5)*2)));
      setLat(v  => +(v + (Math.random()-0.5)*0.0001).toFixed(5));
      setLon(v  => +(v + (Math.random()-0.5)*0.0001).toFixed(5));
    }, 1500);
    return () => clearInterval(t);
  }, []);

  return { alt, speed, bat, sig, lat, lon };
}

export default function MissionDashboard() {
  const { mission, detections, elapsed, paused, setPaused, reset } = useMissionDetections();
  const { alt, speed, bat, sig, lat, lon } = useTelemetry();
  const summary = generateMissionSummary(detections, mission);

  return (
    <div className={styles.root}>
      {/* ── Top nav ──────────────────────────────────── */}
      <MissionHeader
        mission={mission}
        elapsed={elapsed}
        signalStrength={Math.round(sig)}
        battery={Math.round(bat)}
      />

      {/* ── Main content ─────────────────────────────── */}
      <div className={styles.body}>

        {/* LEFT: Camera + controls */}
        <div className={styles.leftCol}>
          <div className={styles.cameraWrap}>
            <CameraFeed altitude={alt} speed={speed} lat={lat} lon={lon}/>
          </div>

          {/* Control strip under camera */}
          <div className={styles.ctrlStrip}>
            <button
              className={`${styles.ctrlBtn} ${paused ? styles.ctrlActive : ""}`}
              onClick={() => setPaused(p => !p)}
              title={paused ? "Resume stream" : "Pause stream"}
            >
              {paused ? <Play size={13}/> : <Pause size={13}/>}
              <span>{paused ? "RESUME" : "PAUSE"}</span>
            </button>
            <button className={styles.ctrlBtn} onClick={reset} title="Clear detections">
              <RotateCcw size={13}/>
              <span>CLEAR</span>
            </button>
            <div className={styles.ctrlDivider}/>
            <div className={styles.detSummaryChips}>
              <span className={styles.chip} style={{ color:"#22c55e",borderColor:"rgba(34,197,94,0.3)",background:"rgba(34,197,94,0.08)" }}>
                {detections.filter(d=>d.detected_class==="healthy").length} HEALTHY
              </span>
              <span className={styles.chip} style={{ color:"#ef4444",borderColor:"rgba(239,68,68,0.3)",background:"rgba(239,68,68,0.08)" }}>
                {detections.filter(d=>d.detected_class!=="healthy").length} DISEASED
              </span>
            </div>
          </div>
        </div>

        {/* CENTER: Detection feed */}
        <div className={styles.centerCol}>
          <DetectionPanel detections={detections}/>
        </div>

        {/* RIGHT: Zone map + complete button */}
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
              <div
                className={styles.healthFill}
                style={{
                  width: `${summary.health_score}%`,
                  background: summary.health_score >= 70 ? "#22c55e" : summary.health_score >= 40 ? "#f59e0b" : "#ef4444",
                }}
              />
              <div className={styles.healthShimmer}/>
            </div>
          </div>

          {/* Zone breakdown mini list */}
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
              {summary.zones_breakdown.filter(z=>z.detection_count>0).length===0 && (
                <div className={styles.noZones}>No active zones yet</div>
              )}
            </div>
          </div>

          {/* Complete Mission CTA */}
          <CompleteMissionButton mission={mission} detections={detections} elapsed={elapsed}/>
        </div>
      </div>

      {/* ── Bottom stats bar ─────────────────────────── */}
      <StatsBar detections={detections} zones={summary.zones_breakdown} healthScore={summary.health_score}/>
    </div>
  );
}
