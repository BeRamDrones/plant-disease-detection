"use client";
import React, { useState, useEffect } from "react";
import { Clock, Activity } from "lucide-react";
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
  const [timeStr, setTimeStr] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const d = new Date();
      setTimeStr(d.toLocaleTimeString("en-US", { hour12: false }) + " UTC");
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const modelColor = modelStatus.ready
    ? (modelStatus.mock_mode ? "#3B82F6" : "#10B981")
    : "#EF4444";

  return (
    <header className={styles.header}>
      {/* ── LEFT: Brand ── */}
      <div className={styles.brand}>
        <div className={styles.logoWrap}>
          <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
            <polygon points="16,2 30,26 2,26" stroke="#38BDF8" strokeWidth="2.2"
              fill="rgba(56,189,248,0.15)" strokeLinejoin="round"/>
            <circle cx="16" cy="18" r="3.5" fill="#38BDF8"/>
            <line x1="16" y1="2" x2="16" y2="10" stroke="#38BDF8" strokeWidth="1.5" strokeDasharray="2 2"/>
          </svg>
        </div>
        <div>
          <div className={styles.title}>PROJECT JATAYU</div>
          <div className={styles.subtitle}>ENTERPRISE MISSION CONTROL PLATFORM</div>
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
          <span className={styles.idLabel}>UAV DRONE</span>
          <span className={styles.idValue}>{mission.drone_id}</span>
        </div>
        <div className={styles.separator}/>
        <div className={styles.missionId}>
          <span className={styles.idLabel}>STATUS</span>
          <span className={styles.statusBadge}>
            <span className={styles.statusDot}/>
            {mission.status.toUpperCase()}
          </span>
        </div>
        <div className={styles.separator}/>
        <div className={styles.missionId}>
          <span className={styles.idLabel}>NEURAL MODEL</span>
          <span className={styles.modelDot} style={{ background: modelColor, boxShadow: `0 0 8px ${modelColor}` }}/>
          <span className={styles.idValue} style={{ color: modelColor, fontSize: "12px" }}>
            {modelStatus.ready
              ? (modelStatus.mock_mode ? "MOCK ENGINE" : `${modelStatus.model_name.toUpperCase()} (${modelStatus.device})`)
              : "INITIALIZING…"}
          </span>
        </div>
      </div>

      {/* ── RIGHT: Telemetry ── */}
      <div className={styles.telemetry}>
        {/* Real-time UTC Clock */}
        <div className={styles.telItem} title="System Clock">
          <Clock size={13} color="#38BDF8"/>
          <span className={styles.telNum} style={{ minWidth: "80px", color: "#F8FAFC" }}>
            {timeStr || "--:--:-- UTC"}
          </span>
        </div>

        <div className={styles.telDivider}/>

        {/* Latency */}
        <div className={styles.telItem} title="Stream Latency">
          <Activity size={13} color="#10B981"/>
          <span className={styles.telNum} style={{ color: "#10B981" }}>12ms</span>
        </div>
      </div>
    </header>
  );
}
