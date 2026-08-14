"use client";
import React, { useMemo } from "react";
import { MapPin, Radar, Layers } from "lucide-react";
import { Detection, ZoneSummary, diseaseColor, severityLabel, getZoneFromCoords } from "@/lib/types";
import styles from "./ZoneMap.module.css";

// Aggregates detections into ONLY the runtime zones that have formed dynamically
function buildRuntimeZones(detections: Detection[]): ZoneSummary[] {
  const zoneMap: Record<string, Detection[]> = {};

  for (const d of detections) {
    const zone = d.zone_label ? { zone_label: d.zone_label } : getZoneFromCoords(d.lat, d.lon);
    const label = zone.zone_label;
    if (!zoneMap[label]) zoneMap[label] = [];
    zoneMap[label].push(d);
  }

  const summaries: ZoneSummary[] = [];
  let idx = 1;
  for (const [label, dets] of Object.entries(zoneMap)) {
    const counts: Record<string, number> = {};
    for (const d of dets) counts[d.detected_class] = (counts[d.detected_class] ?? 0) + 1;
    const dominant = dets.length
      ? Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]
      : null;

    const avgConf = dets.length
      ? dets.reduce((s, d) => s + d.confidence_score, 0) / dets.length
      : 0;

    summaries.push({
      zone_id:         idx++,
      zone_label:      label,
      dominant_class:  dominant,
      detection_count: dets.length,
      avg_confidence:  avgConf,
    });
  }

  return summaries;
}

interface Props {
  zones?: ZoneSummary[];
  detections?: Detection[];
}

function RuntimeZoneCell({ zone }: { zone: ZoneSummary }) {
  const color  = diseaseColor(zone.dominant_class ?? "");
  const sev    = severityLabel(zone.dominant_class ?? "");

  return (
    <div
      className={styles.cell}
      style={{
        "--zone-color": color,
        borderColor: `${color}60`,
        background:  `${color}18`,
      } as React.CSSProperties}
      title={`${zone.zone_label}: ${(zone.dominant_class ?? "").replace(/_/g," ").toUpperCase()} · ${zone.detection_count} detections`}
    >
      <div className={styles.cellGlow} style={{ background: color }}/>
      
      <div className={styles.cellTop}>
        <span className={styles.cellLabel} style={{ color }}>
          ZONE {zone.zone_label}
        </span>
        <span className={styles.formedBadge}>LIVE FORMED</span>
      </div>

      <div className={styles.cellBody}>
        <span className={styles.classText} style={{ color }}>
          {(zone.dominant_class ?? "UNCLASSIFIED").replace(/_/g," ").toUpperCase()}
        </span>
        <div className={styles.countBadge} style={{ color, borderColor: `${color}40`, background: `${color}12` }}>
          {zone.detection_count} {zone.detection_count === 1 ? "DETECTION" : "DETECTIONS"}
        </div>
      </div>

      <div className={styles.confBar}>
        <div
          className={styles.confFill}
          style={{ width: `${Math.min(100, Math.max(10, zone.avg_confidence * 100))}%`, background: color }}
        />
      </div>
    </div>
  );
}

export default function ZoneMap({ zones: propZones, detections = [] }: Props) {
  // Dynamically form zones at runtime from actual incoming detections
  const activeZones = useMemo(() => {
    if (detections.length > 0) return buildRuntimeZones(detections);
    if (propZones && propZones.some(z => z.detection_count > 0)) {
      return propZones.filter(z => z.detection_count > 0);
    }
    return [];
  }, [detections, propZones]);

  const totalDets = detections.length;

  return (
    <div className={styles.wrap}>
      {/* ── Header ── */}
      <div className={styles.hdr}>
        <div className={styles.hdrLeft}>
          <MapPin size={15} color="#38BDF8"/>
          <span className={styles.title}>FIELD SURVEY ZONES</span>
        </div>
        <div className={styles.hdrRight}>
          {activeZones.length === 0 ? (
            <span className={styles.scanBadge}>
              DISCOVERY ACTIVE
            </span>
          ) : (
            <span className={styles.activeBadge}>{activeZones.length} RUNTIME ZONE(S) FORMED</span>
          )}
        </div>
      </div>

      {/* Grid view when runtime zones have formed */}
      {activeZones.length > 0 ? (
        <div className={styles.grid}>
          {activeZones.map(zone => (
            <RuntimeZoneCell key={zone.zone_label} zone={zone} />
          ))}
        </div>
      ) : (
        /* Standby state when no field zones have formed yet */
        <div className={styles.emptyState}>
          <div className={styles.radarWrapper}>
            <Radar size={32} color="rgba(0,240,255,0.4)" className={styles.radarSpin}/>
            <div className={styles.radarPulse}/>
          </div>
          <span className={styles.emptyTitle}>NO RUNTIME ZONES FORMED YET</span>
          <span className={styles.emptySub}>
            Zones form dynamically at runtime as the drone scans and discovers targets across field sectors.
          </span>
        </div>
      )}

      {/* Footer stats */}
      <div className={styles.footer}>
        {totalDets === 0 ? (
          <span className={styles.footerEmpty}>
            Awaiting spatial telemetry — 0 field zones formed
          </span>
        ) : (
          <div className={styles.footStat}>
            <MapPin size={10} color="#00F0FF"/>
            <span style={{ color: "#00F0FF" }}>
              {activeZones.length} Sector Zone(s) Formed · {totalDets} Total Detections
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
