"use client";
import React, { useState, useMemo } from "react";
import { AlertTriangle, CheckCircle, Activity, Cpu, VideoOff, ChevronDown, ChevronUp, ShieldAlert, Copy, Check } from "lucide-react";
import { Detection, diseaseColor, severityLabel, getTreatmentAdvisory } from "@/lib/types";
import styles from "./DetectionPanel.module.css";

interface Props { detections: Detection[]; modelReady: boolean; totalScans?: number; cameraOff?: boolean; }

function ConfBar({ val }: { val: number }) {
  const color = val >= 0.9 ? "#00F0FF" : val >= 0.75 ? "#3B82F6" : "#FF2D95";
  return (
    <div className={styles.confBar}>
      <div className={styles.confFill} style={{ width: `${val * 100}%`, background: `linear-gradient(90deg, #00F0FF 0%, ${color} 100%)` }}/>
    </div>
  );
}

function DetectionCard({ det, index }: { det: Detection; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const color  = diseaseColor(det.detected_class);
  const sev    = severityLabel(det.detected_class);
  const isOk   = det.detected_class === "healthy";
  const Icon   = isOk ? CheckCircle : AlertTriangle;
  const time   = new Date(det.detected_at).toLocaleTimeString("en-IN", { hour12: false });
  const advisory = getTreatmentAdvisory(det.detected_class);

  const copyGps = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(`${det.lat.toFixed(5)}, ${det.lon.toFixed(5)}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`${styles.card} ${expanded ? styles.cardExpanded : ""}`}
      style={{ animationDelay: `${Math.min(index, 5) * 0.06}s`, borderLeftColor: color }}
      onClick={() => setExpanded(e => !e)}
    >
      <div className={styles.cardTop}>
        <div className={styles.cardLeft}>
          <Icon size={15} color={color} strokeWidth={2.2}/>
          <div>
            <div className={styles.classLabel} style={{ color }}>
              {det.detected_class.replace(/_/g, " ").toUpperCase()}
            </div>
            <div className={styles.zoneLine}>
              {det.zone_label && <span className={styles.zoneChip}>Zone {det.zone_label}</span>}
              {det.grid_zone && <span className={styles.gridChip}>{det.grid_zone.toUpperCase()}</span>}
              {det.rank && (
                <span className={styles.rankChip}>#{det.rank}</span>
              )}
              <span className={styles.sevChip} style={{ color, borderColor: `${color}40`, background: `${color}15` }}>
                {sev}
              </span>
            </div>
          </div>
        </div>
        <div className={styles.cardRight}>
          <div className={styles.confPct} style={{ color }}>
            {(det.confidence_score * 100).toFixed(1)}%
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span className={styles.timestamp}>{time}</span>
            {expanded ? <ChevronUp size={13} color="var(--text-muted)"/> : <ChevronDown size={13} color="var(--text-muted)"/>}
          </div>
        </div>
      </div>

      <ConfBar val={det.confidence_score}/>

      {expanded && (
        <div className={styles.advisoryBox}>
          <div className={styles.advisoryHeader}>
            <ShieldAlert size={13} color={color}/>
            <span className={styles.advisoryTitle} style={{ color }}>AGRONOMIC ADVISORY & REMEDY</span>
          </div>
          <div className={styles.advisoryAction}>{advisory.action}</div>
          <div className={styles.advisoryRemedy}>{advisory.remedy}</div>
        </div>
      )}

      <div className={styles.cardBottom}>
        <button className={styles.gpsSmallBtn} onClick={copyGps} title="Click to copy GPS coordinates">
          {copied ? <Check size={10} color="#10B981"/> : <Copy size={10} color="var(--text-muted)"/>}
          <span>{det.lat.toFixed(4)}°N &nbsp;{det.lon.toFixed(4)}°E</span>
        </button>
        <span className={styles.modelVer}>
          {expanded ? "Collapse details" : "Click for advisory"}
        </span>
      </div>
    </div>
  );
}

export default function DetectionPanel({ detections, modelReady, totalScans = 0, cameraOff = false }: Props) {
  const [filter, setFilter] = useState<"all" | "diseased" | "healthy">("all");

  const cropCount = detections.filter(d => severityLabel(d.detected_class) === "CROP ID").length;
  const diseaseCount = detections.filter(d => ["CRITICAL", "HIGH", "MODERATE"].includes(severityLabel(d.detected_class))).length;
  const healthyCount = detections.filter(d => d.detected_class === "healthy").length;

  const filteredDetections = useMemo(() => {
    return detections.filter(d => {
      if (filter === "diseased") return ["CRITICAL", "HIGH", "MODERATE"].includes(severityLabel(d.detected_class));
      if (filter === "healthy") return d.detected_class === "healthy";
      return true;
    });
  }, [detections, filter]);

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Activity size={15} color="#00F0FF"/>
          <span className={styles.headerTitle}>LIVE DETECTIONS FEED</span>
        </div>
        <div className={styles.headerStats}>
          {diseaseCount > 0 || healthyCount > 0 ? (
            <>
              <button
                className={`${styles.statPillBtn} ${filter === "healthy" ? styles.statPillActive : ""}`}
                style={{ color: "#00F0FF", borderColor: "rgba(0,240,255,0.3)" }}
                onClick={() => setFilter(f => f === "healthy" ? "all" : "healthy")}
              >
                {healthyCount} OK
              </button>
              <button
                className={`${styles.statPillBtn} ${filter === "diseased" ? styles.statPillActive : ""}`}
                style={{ color: "#FF2D95", borderColor: "rgba(255,45,149,0.4)" }}
                onClick={() => setFilter(f => f === "diseased" ? "all" : "diseased")}
              >
                {diseaseCount} DISEASED
              </button>
            </>
          ) : (
            <span className={styles.statPill} style={{ color: "#00F0FF", background: "rgba(0,240,255,0.1)", borderColor: "rgba(0,240,255,0.3)" }}>
              {cropCount} CROPS
            </span>
          )}
        </div>
      </div>

      {/* Live indicator */}
      <div className={styles.liveBar}>
        <span className={`${styles.liveDot} ${(!modelReady || cameraOff) ? styles.liveDotWaiting : ""}`}/>
        <span className={styles.liveText}>
          {!modelReady
            ? "INITIALIZING NEURAL ENGINE…"
            : cameraOff
              ? "STREAM OFFLINE — INFERENCE PAUSED"
              : totalScans === 0
                ? "PIPELINE READY — SUBMIT IMAGE / VIDEO / LIVE UAV FRAME"
                : `${totalScans} SCANS COMPLETED · ${filteredDetections.length} DISPLAYED`
          }
        </span>
      </div>

      {/* Cards Feed */}
      <div className={styles.list}>
        {!modelReady ? (
          <div className={styles.empty}>
            <Cpu size={32} color="rgba(59,130,246,0.4)"/>
            <span style={{ color: "#3B82F6" }}>Loading Parent Model (best.pt)…</span>
            <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Neural inference engine will begin scanning on GPU</span>
          </div>
        ) : cameraOff ? (
          <div className={styles.empty}>
            <VideoOff size={32} color="rgba(255,45,149,0.3)"/>
            <span style={{ color: "#FF2D95" }}>Camera Stream Offline</span>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "center", lineHeight: 1.5 }}>
              The UAV camera stream is closed.{"\n"}Enable feed toggle to start continuous AI detection.
            </span>
          </div>
        ) : filteredDetections.length === 0 ? (
          <div className={styles.empty}>
            <Activity size={32} color="rgba(0,240,255,0.2)"/>
            <span>No Detections Recorded</span>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "center", lineHeight: 1.5 }}>
              {filter !== "all" ? `No ${filter} detections match filter` : "Upload an image, start video scan,\nor capture a live UAV stream frame"}
            </span>
          </div>
        ) : (
          filteredDetections.map((d, i) => <DetectionCard key={d.id} det={d} index={i}/>)
        )}
      </div>
    </div>
  );
}
