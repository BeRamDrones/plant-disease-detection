"use client";
import React from "react";
import { AlertTriangle, CheckCircle, Activity } from "lucide-react";
import { Detection, diseaseColor, severityLabel } from "@/lib/types";
import styles from "./DetectionPanel.module.css";

interface Props { detections: Detection[]; }

function ConfBar({ val }: { val: number }) {
  const color = val >= 0.9 ? "#22c55e" : val >= 0.75 ? "#f59e0b" : "#ef4444";
  return (
    <div className={styles.confBar}>
      <div className={styles.confFill} style={{ width:`${val*100}%`, background:color }}/>
    </div>
  );
}

function DetectionCard({ det, index }: { det: Detection; index: number }) {
  const color  = diseaseColor(det.detected_class);
  const sev    = severityLabel(det.detected_class);
  const isOk   = det.detected_class === "healthy";
  const Icon   = isOk ? CheckCircle : AlertTriangle;
  const time   = new Date(det.detected_at).toLocaleTimeString("en-IN", { hour12:false });

  return (
    <div
      className={styles.card}
      style={{ animationDelay: `${Math.min(index,5)*0.06}s`, borderLeftColor: color }}
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
          <div className={styles.timestamp}>{time}</div>
        </div>
      </div>

      <ConfBar val={det.confidence_score}/>

      <div className={styles.cardBottom}>
        <span className={styles.gpsSmall}>
          {det.lat.toFixed(4)}°N&nbsp;&nbsp;{det.lon.toFixed(4)}°E
        </span>
        <span className={styles.modelVer}>{det.model_version}</span>
      </div>
    </div>
  );
}

export default function DetectionPanel({ detections }: Props) {
  const diseaseCount = detections.filter(d => d.detected_class !== "healthy").length;
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
          <span className={styles.statPill} style={{ color:"#22c55e", background:"rgba(34,197,94,0.1)", borderColor:"rgba(34,197,94,0.25)" }}>
            {healthyCount} OK
          </span>
          <span className={styles.statPill} style={{ color:"#ef4444", background:"rgba(239,68,68,0.1)", borderColor:"rgba(239,68,68,0.25)" }}>
            {diseaseCount} DISEASED
          </span>
        </div>
      </div>

      {/* Live indicator */}
      <div className={styles.liveBar}>
        <span className={styles.liveDot}/>
        <span className={styles.liveText}>STREAMING — {detections.length} TOTAL</span>
      </div>

      {/* Cards */}
      <div className={styles.list}>
        {detections.length === 0 ? (
          <div className={styles.empty}>
            <Activity size={28} color="rgba(0,212,255,0.2)"/>
            <span>Awaiting detections…</span>
          </div>
        ) : (
          detections.map((d, i) => <DetectionCard key={d.id} det={d} index={i}/>)
        )}
      </div>
    </div>
  );
}
