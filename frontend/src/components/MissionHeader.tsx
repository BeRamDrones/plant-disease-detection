"use client";
import React from "react";
import { Satellite, Battery, Gauge, Wind } from "lucide-react";
import { MissionData } from "@/lib/types";
import { ModelStatus } from "@/hooks/useModelStatus";
import styles from "./MissionHeader.module.css";

interface Props {
  mission: MissionData;
  elapsed: number;
  signalStrength: number;
  battery: number;
  modelStatus: ModelStatus;
  altitude?: number;
  speed?: number;
}

export default function MissionHeader({
  mission, signalStrength, battery, modelStatus, altitude = 0, speed = 0,
}: Props) {
  const batColor = battery > 50 ? "#22c55e" : battery > 20 ? "#f59e0b" : "#ef4444";
  const sigBars  = Math.ceil(signalStrength / 20);

  const modelColor = modelStatus.ready
    ? (modelStatus.mock_mode ? "#f59e0b" : "#22c55e")
    : "#f59e0b";

  return (
    <header className={styles.header}>
      {/* ── LEFT: Brand ── */}
      <div className={styles.brand}>
        <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
          <polygon points="16,2 30,26 2,26" stroke="#06b6d4" strokeWidth="1.5"
            fill="rgba(6,182,212,0.08)" strokeLinejoin="round"/>
          <circle cx="16" cy="18" r="3" fill="#06b6d4"/>
          <line x1="16" y1="2" x2="16" y2="10" stroke="#06b6d4" strokeWidth="1" strokeDasharray="2 2"/>
        </svg>
        <div>
          <div className={styles.title}>PROJECT JATAYU</div>
          <div className={styles.subtitle}>MISSION CONTROL</div>
        </div>
      </div>

      {/* ── CENTER: Mission identifiers ── */}
      <div className={styles.center}>
        <div className={styles.missionId}>
          <span className={styles.idLabel}>MISSION</span>
          <span className={styles.idValue}>#{mission.mission_id}</span>
        </div>
        <div className={styles.separator}/>
        <div className={styles.missionId}>
          <span className={styles.idLabel}>DRONE</span>
          <span className={styles.idValue}>{mission.drone_id}</span>
        </div>
        <div className={styles.separator}/>
        {/* Model ready indicator — minimal dot only */}
        <div className={styles.missionId}>
          <div
            className={styles.modelDot}
            style={{ background: modelColor, boxShadow: `0 0 8px ${modelColor}` }}
            title={modelStatus.ready ? (modelStatus.mock_mode ? "Mock mode" : `Model ready (${modelStatus.model_task})`) : "Loading model…"}
          />
          <span className={styles.idLabel} style={{ color: modelColor }}>
            {modelStatus.ready ? (modelStatus.mock_mode ? "MOCK" : "MODEL") : "LOADING"}
          </span>
        </div>
      </div>

      {/* ── RIGHT: Telemetry ── */}
      <div className={styles.telemetry}>

        {/* Altitude */}
        <div className={styles.telItem}>
          <Gauge size={12} color="#94a3b8"/>
          <div className={styles.telVal}>
            <span className={styles.telNum}>{altitude.toFixed(0)}</span>
            <span className={styles.telUnit}>m</span>
          </div>
        </div>

        {/* Speed */}
        <div className={styles.telItem}>
          <Wind size={12} color="#94a3b8"/>
          <div className={styles.telVal}>
            <span className={styles.telNum}>{speed.toFixed(1)}</span>
            <span className={styles.telUnit}>m/s</span>
          </div>
        </div>

        <div className={styles.telDivider}/>

        {/* Signal bars */}
        <div className={styles.telItem}>
          <Satellite size={12} color="#94a3b8"/>
          <div className={styles.bars}>
            {[1,2,3,4,5].map(i => (
              <div key={i} className={styles.bar} style={{
                height: `${i * 3 + 3}px`,
                background: i <= sigBars ? "#06b6d4" : "rgba(255,255,255,0.1)",
              }}/>
            ))}
          </div>
          <span className={styles.telSmall}>{signalStrength}%</span>
        </div>

        {/* Battery */}
        <div className={styles.telItem}>
          <Battery size={12} color={batColor}/>
          <div className={styles.batOuter}>
            <div className={styles.batInner} style={{ width: `${battery}%`, background: batColor }}/>
          </div>
          <span className={styles.telSmall} style={{ color: batColor }}>{battery}%</span>
        </div>
      </div>
    </header>
  );
}
