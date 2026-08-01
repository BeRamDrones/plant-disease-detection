"use client";
import React from "react";
import { Shield, AlertTriangle, Activity, Layers } from "lucide-react";
import { Detection, ZoneSummary } from "@/lib/types";
import styles from "./StatsBar.module.css";

interface Props { detections: Detection[]; zones: ZoneSummary[]; healthScore: number; }

export default function StatsBar({ detections, zones, healthScore }: Props) {
  const diseased   = detections.filter(d => d.detected_class !== "healthy");
  const classMap   = Object.fromEntries(
    Object.entries(
      detections.reduce((acc, d) => {
        acc[d.detected_class] = (acc[d.detected_class] ?? 0) + 1;
        return acc;
      }, {} as Record<string,number>)
    ).sort((a,b) => b[1]-a[1])
  );
  const dominant   = Object.keys(classMap)[0] ?? "—";
  const zonesActive = zones.filter(z => z.detection_count > 0).length;
  const hsColor    = healthScore >= 70 ? "#22c55e" : healthScore >= 40 ? "#f59e0b" : "#ef4444";

  const stats = [
    {
      icon: <Activity size={16} color="#00d4ff"/>,
      label: "TOTAL DETECTIONS",
      value: detections.length.toString(),
      color: "#00d4ff",
    },
    {
      icon: <AlertTriangle size={16} color="#ef4444"/>,
      label: "DISEASED ALERTS",
      value: diseased.length.toString(),
      color: "#ef4444",
    },
    {
      icon: <Layers size={16} color="#a855f7"/>,
      label: "ZONES ACTIVE",
      value: `${zonesActive} / ${zones.length}`,
      color: "#a855f7",
    },
    {
      icon: <Shield size={16} color={hsColor}/>,
      label: "HEALTH SCORE",
      value: `${healthScore.toFixed(1)}%`,
      color: hsColor,
    },
  ];

  return (
    <div className={styles.bar}>
      {stats.map((s, i) => (
        <React.Fragment key={s.label}>
          <div className={styles.statBlock}>
            {s.icon}
            <div className={styles.statContent}>
              <span className={styles.statLabel}>{s.label}</span>
              <span className={styles.statValue} style={{ color: s.color }}>{s.value}</span>
            </div>
          </div>
          {i < stats.length - 1 && <div className={styles.divider}/>}
        </React.Fragment>
      ))}

      {/* Dominant disease */}
      <div className={styles.divider}/>
      <div className={styles.statBlock}>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>DOMINANT DISEASE</span>
          <span className={styles.statValue} style={{ color:"#f59e0b", fontSize:"11px" }}>
            {dominant.replace(/_/g," ").toUpperCase()}
          </span>
        </div>
      </div>
    </div>
  );
}
