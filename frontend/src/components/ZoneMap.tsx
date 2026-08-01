"use client";
import React from "react";
import { ZoneSummary, diseaseColor } from "@/lib/types";
import { Map } from "lucide-react";
import styles from "./ZoneMap.module.css";

interface Props { zones: ZoneSummary[]; }

const GRID_COLS = ["A","B","C","D"];
const GRID_ROWS = ["1","2"];

export default function ZoneMap({ zones }: Props) {
  const zoneByLabel = Object.fromEntries(zones.map(z => [z.zone_label, z]));

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <Map size={12} color="#00d4ff"/>
        <span className={styles.title}>ZONE MAP</span>
      </div>
      <div className={styles.grid}>
        {GRID_COLS.map(col =>
          GRID_ROWS.map(row => {
            const label = `${col}${row}`;
            const zone  = zoneByLabel[label];
            const color = zone?.dominant_class ? diseaseColor(zone.dominant_class) : "rgba(255,255,255,0.06)";
            const isActive = zone && zone.detection_count > 0;
            return (
              <div
                key={label}
                className={`${styles.cell} ${isActive ? styles.active : ""}`}
                style={{
                  "--zone-color": color,
                  background: isActive ? `${color}20` : "rgba(255,255,255,0.03)",
                  borderColor:  isActive ? `${color}50` : "rgba(255,255,255,0.06)",
                } as React.CSSProperties}
                title={zone ? `${label}: ${zone.dominant_class ?? "no detections"} (${zone.detection_count} dets)` : label}
              >
                <span className={styles.cellLabel}>{label}</span>
                {isActive && (
                  <span className={styles.detCount} style={{ color }}>
                    {zone.detection_count}
                  </span>
                )}
                {isActive && <div className={styles.cellGlow} style={{ background: color }}/>}
              </div>
            );
          })
        )}
      </div>
      {/* Legend */}
      <div className={styles.legend}>
        {[["#22c55e","Healthy"],["#f59e0b","Moderate"],["#ef4444","Critical"]].map(([c,l]) => (
          <div key={l} className={styles.legendItem}>
            <div className={styles.legendDot} style={{ background:c }}/>
            <span>{l}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
