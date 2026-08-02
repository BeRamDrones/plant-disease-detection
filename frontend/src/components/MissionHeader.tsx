"use client";
import React from "react";
import { Wifi, Battery, Satellite, Navigation, Cpu, CheckCircle, Loader } from "lucide-react";
import { MissionData } from "@/lib/types";
import { ModelStatus } from "@/hooks/useModelStatus";
import { formatElapsed } from "@/hooks/useMissionDetections";
import styles from "./MissionHeader.module.css";

interface Props {
  mission: MissionData;
  elapsed: number;
  signalStrength: number;
  battery: number;
  modelStatus: ModelStatus;
}

export default function MissionHeader({ mission, elapsed, signalStrength, battery, modelStatus }: Props) {
  const phaseColor  = mission.phase === "detection" ? "#00d4ff" : "#f59e0b";
  const statusColor = mission.status === "in_progress" ? "#22c55e" : "#f59e0b";
  const batColor    = battery > 50 ? "#22c55e" : battery > 20 ? "#f59e0b" : "#ef4444";

  const modelColor  = modelStatus.ready
    ? (modelStatus.mock_mode ? "#f59e0b" : "#22c55e")
    : "#f59e0b";
  const ModelIcon   = modelStatus.ready ? CheckCircle : Loader;
  const modelLabel  = modelStatus.ready
    ? (modelStatus.mock_mode ? "MOCK" : "READY")
    : "LOADING";

  return (
    <header className={styles.header}>
      {/* ── Left: Branding ── */}
      <div className={styles.brand}>
        <div className={styles.logo}>
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
            <polygon points="16,2 30,26 2,26" stroke="#00d4ff" strokeWidth="1.5"
              fill="rgba(0,212,255,0.08)" strokeLinejoin="round"/>
            <circle cx="16" cy="18" r="3" fill="#00d4ff"/>
            <line x1="16" y1="2" x2="16" y2="10" stroke="#00d4ff" strokeWidth="1" strokeDasharray="2 2"/>
          </svg>
        </div>
        <div>
          <div className={styles.title}>PROJECT JATAYU</div>
          <div className={styles.subtitle}>MISSION CONTROL</div>
        </div>
      </div>

      {/* ── Center: Mission info ── */}
      <div className={styles.center}>
        <div className={styles.infoRow}>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>MISSION</span>
            <span className={styles.infoValue}>#{mission.mission_id}</span>
          </div>
          <div className={styles.divider}/>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>DRONE</span>
            <span className={styles.infoValue}>{mission.drone_id}</span>
          </div>
          <div className={styles.divider}/>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>PHASE</span>
            <span className={styles.infoValue} style={{ color: phaseColor }}>{mission.phase.toUpperCase()}</span>
          </div>
          <div className={styles.divider}/>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>STATUS</span>
            <span className={styles.statusDot} style={{ background: statusColor }}/>
            <span className={styles.infoValue} style={{ color: statusColor }}>
              {mission.status.replace("_"," ").toUpperCase()}
            </span>
          </div>
          <div className={styles.divider}/>
          {/* Model status pill */}
          <div className={styles.infoItem}>
            <Cpu size={10} color={modelColor} />
            <span className={styles.infoLabel}>MODEL</span>
            <span
              className={`${styles.modelPill} ${modelStatus.ready ? styles.modelReady : styles.modelLoading}`}
              style={{ color: modelColor, borderColor: `${modelColor}40`, background: `${modelColor}12` }}
            >
              {!modelStatus.ready && (
                <ModelIcon size={8} color={modelColor}
                  className={styles.modelSpinIcon} strokeWidth={2}/>
              )}
              {modelStatus.ready && (
                <ModelIcon size={8} color={modelColor} strokeWidth={2}/>
              )}
              {modelLabel}
            </span>
          </div>
        </div>

        {/* Elapsed timer */}
        <div className={styles.timer}>{formatElapsed(elapsed)}</div>
      </div>

      {/* ── Right: Telemetry ── */}
      <div className={styles.telemetry}>
        {/* Signal */}
        <div className={styles.telItem}>
          <Satellite size={13} color="#94a3b8"/>
          <div className={styles.telBars}>
            {[1,2,3,4,5].map(i => (
              <div key={i} className={styles.bar} style={{
                height: `${i*3+3}px`,
                background: i <= Math.ceil(signalStrength/20) ? "#00d4ff" : "rgba(255,255,255,0.1)"
              }}/>
            ))}
          </div>
          <span className={styles.telLabel}>{signalStrength}%</span>
        </div>

        {/* Battery */}
        <div className={styles.telItem}>
          <Battery size={13} color={batColor}/>
          <div className={styles.batOuter}>
            <div className={styles.batInner} style={{ width:`${battery}%`, background:batColor }}/>
          </div>
          <span className={styles.telLabel} style={{ color:batColor }}>{battery}%</span>
        </div>

        {/* Crop class */}
        <div className={styles.telItem}>
          <Navigation size={13} color="#a855f7"/>
          <span className={styles.telLabel} style={{ color:"#a855f7" }}>
            {mission.crop_class?.toUpperCase() ?? "N/A"}
          </span>
        </div>
      </div>
    </header>
  );
}
