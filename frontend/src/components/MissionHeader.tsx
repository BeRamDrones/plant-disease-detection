"use client";
import React from "react";
import { Satellite, Battery } from "lucide-react";
import { MissionData } from "@/lib/types";
import { ModelStatus } from "@/hooks/useModelStatus";
import styles from "./MissionHeader.module.css";

interface Props {
  mission: MissionData;
  elapsed: number;
  signalStrength: number;
  battery: number;
  modelStatus: ModelStatus;
}

export default function MissionHeader({
  mission, signalStrength, battery, modelStatus, elapsed,
}: Props) {
  const batColor = battery > 50 ? "#00F0FF" : battery > 20 ? "#3B82F6" : "#FF2D95";
  const sigBars  = Math.ceil(signalStrength / 20);

  const modelColor = modelStatus.ready
    ? (modelStatus.mock_mode ? "#3B82F6" : "#00F0FF")
    : "#FF2D95";

  return (
    <header className={styles.header}>
      {/* ── LEFT: Brand ── */}
      <div className={styles.brand}>
        <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
          <polygon points="16,2 30,26 2,26" stroke="#00F0FF" strokeWidth="1.5"
            fill="rgba(0,240,255,0.08)" strokeLinejoin="round"/>
          <circle cx="16" cy="18" r="3" fill="#00F0FF"/>
          <line x1="16" y1="2" x2="16" y2="10" stroke="#00F0FF" strokeWidth="1" strokeDasharray="2 2"/>
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
        <div className={styles.missionId}>
          <span className={styles.idLabel}>STATUS</span>
          <span className={styles.idValue} style={{ color: "#00F0FF" }}>
            {mission.status.toUpperCase()}
          </span>
        </div>
        <div className={styles.separator}/>
        <div className={styles.missionId}>
          <span className={styles.idLabel}>MODEL</span>
          <span className={styles.modelDot} style={{ background: modelColor }}/>
          <span className={styles.idValue} style={{ color: modelColor, fontSize: "9px" }}>
            {modelStatus.ready
              ? (modelStatus.mock_mode ? "MOCK DETECT" : modelStatus.model_name.toUpperCase())
              : "CONNECTING…"}
          </span>
        </div>
      </div>

      {/* ── RIGHT: Drone Telemetry ── */}
      <div className={styles.telemetry}>
        {/* Signal */}
        <div className={styles.telItem} title={`Signal: ${signalStrength}%`}>
          <Satellite size={12} color="#00F0FF"/>
          <div className={styles.bars}>
            {[1,2,3,4,5].map(i => (
              <div key={i} className={styles.bar} style={{
                height: `${i * 3 + 1}px`,
                background: i <= sigBars ? "#00F0FF" : "rgba(0,240,255,0.15)",
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
