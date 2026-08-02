"use client";
import React, { useState } from "react";
import { AlertTriangle, CheckCircle, Activity, Cpu, VideoOff, ChevronDown, ChevronUp, ShieldAlert, Sparkles } from "lucide-react";
import { Detection, diseaseColor, severityLabel, getTreatmentAdvisory } from "@/lib/types";
import styles from "./DetectionPanel.module.css";

interface Props { detections: Detection[]; modelReady: boolean; totalScans?: number; cameraOff?: boolean; }

function ConfBar({ val }: { val: number }) {
  const color = val >= 0.9 ? "#22c55e" : val >= 0.75 ? "#f59e0b" : "#ef4444";
  return (
    <div className={styles.confBar}>
      <div className={styles.confFill} style={{ width:`${val*100}%`, background:color }}/>
    </div>
  );
}

function DetectionCard({ det, index }: { det: Detection; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const color  = diseaseColor(det.detected_class);
  const sev    = severityLabel(det.detected_class);
  const isOk   = det.detected_class === "healthy";
  const Icon   = isOk ? CheckCircle : AlertTriangle;
  const time   = new Date(det.detected_at).toLocaleTimeString("en-IN", { hour12:false });
  const advisory = getTreatmentAdvisory(det.detected_class);

  return (
    <div
      className={`${styles.card} ${expanded ? styles.cardExpanded : ""}`}
      style={{ animationDelay: `${Math.min(index,5)*0.06}s`, borderLeftColor: color }}
      onClick={() => setExpanded(e => !e)}
    >
      <div className={styles.cardTop}>
        <div className={styles.cardLeft}>
          <Icon size={14} color={color} strokeWidth={2}/>
          <div>
            <div className={styles.classLabel} style={{ color }}>
              {det.detected_class.replace(/_/g," ").toUpperCase()}
            </div>
            <div className={styles.zoneLine}>
              {det.zone_label && <span className={styles.zoneChip}>Zone {det.zone_label}</span>}
              {det.rank && (
                <span className={styles.rankChip}>#{det.rank}</span>
              )}
              <span className={styles.sevChip} style={{ color, borderColor:`${color}40`, background:`${color}12` }}>
                {sev}
              </span>
            </div>
          </div>
        </div>
        <div className={styles.cardRight}>
          <div className={styles.confPct} style={{ color }}>
            {(det.confidence_score*100).toFixed(1)}%
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span className={styles.timestamp}>{time}</span>
            {expanded ? <ChevronUp size={12} color="var(--text-muted)"/> : <ChevronDown size={12} color="var(--text-muted)"/>}
          </div>
        </div>
      </div>

      <ConfBar val={det.confidence_score}/>

      {expanded && (
        <div className={styles.advisoryBox}>
          <div className={styles.advisoryHeader}>
            <ShieldAlert size={11} color={color}/>
            <span className={styles.advisoryTitle} style={{ color }}>RECOMMENDED ACTION</span>
          </div>
          <div className={styles.advisoryAction}>{advisory.action}</div>
          <div className={styles.advisoryRemedy}>{advisory.remedy}</div>
        </div>
      )}

      <div className={styles.cardBottom}>
        <span className={styles.gpsSmall}>
          {det.lat.toFixed(4)}°N&nbsp;&nbsp;{det.lon.toFixed(4)}°E
        </span>
        <span className={styles.modelVer}>
          {expanded ? "Click to collapse" : "Click for advice"}
        </span>
      </div>
    </div>
  );
}

export default function DetectionPanel({ detections, modelReady, totalScans = 0, cameraOff = false }: Props) {
  const cropCount = detections.filter(d => severityLabel(d.detected_class) === "CROP ID").length;
  const diseaseCount = detections.filter(d => ["CRITICAL", "HIGH", "MODERATE"].includes(severityLabel(d.detected_class))).length;
  const healthyCount = detections.filter(d => d.detected_class === "healthy").length;

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Activity size={14} color="#00d4ff"/>
          <span className={styles.headerTitle}>LIVE DETECTIONS</span>
        </div>
        <div className={styles.headerStats}>
          {diseaseCount > 0 || healthyCount > 0 ? (
            <>
              <span className={styles.statPill} style={{ color:"#22c55e", background:"rgba(34,197,94,0.1)", borderColor:"rgba(34,197,94,0.25)" }}>
                {healthyCount} OK
              </span>
              <span className={styles.statPill} style={{ color:"#ef4444", background:"rgba(239,68,68,0.1)", borderColor:"rgba(239,68,68,0.25)" }}>
                {diseaseCount} DISEASED
              </span>
            </>
          ) : (
            <span className={styles.statPill} style={{ color:"#00d4ff", background:"rgba(0,212,255,0.1)", borderColor:"rgba(0,212,255,0.25)" }}>
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
            ? "AWAITING MODEL…"
            : cameraOff
              ? "CAMERA OFFLINE — NO DETECTION RUNNING"
              : totalScans === 0
                ? "MODEL READY — SUBMIT IMAGE / VIDEO / LIVE FRAME TO BEGIN"
                : `${totalScans} SCAN(S) · ${detections.length} TOTAL DETECTIONS`
          }
        </span>
      </div>

      {/* Cards */}
      <div className={styles.list}>
        {!modelReady ? (
          <div className={styles.empty}>
            <Cpu size={28} color="rgba(245,158,11,0.3)"/>
            <span style={{ color:"#f59e0b" }}>Loading parent model (best.pt)…</span>
            <span style={{ fontSize:"10px", color:"var(--text-muted)" }}>Detection will begin once the model is ready</span>
          </div>
        ) : cameraOff ? (
          <div className={styles.empty}>
            <VideoOff size={28} color="rgba(239,68,68,0.25)"/>
            <span style={{ color:"#ef4444" }}>No Camera Detected</span>
            <span style={{ fontSize:"10px", color:"var(--text-muted)", textAlign:"center", lineHeight:1.5 }}>
              The UAV camera stream is offline.{"\n"}Enable the camera feed to begin AI detection.
            </span>
          </div>
        ) : detections.length === 0 ? (
          <div className={styles.empty}>
            <Activity size={28} color="rgba(0,212,255,0.2)"/>
            <span>No detections yet</span>
            <span style={{ fontSize:"10px", color:"var(--text-muted)", textAlign:"center", lineHeight:1.5 }}>
              Upload an image, start video scan,{"\n"}or capture a live UAV frame
            </span>
          </div>
        ) : (
          detections.map((d, i) => <DetectionCard key={d.id} det={d} index={i}/>)
        )}
      </div>
    </div>
  );
}
