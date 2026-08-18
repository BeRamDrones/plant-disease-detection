import React from "react";
import { Shield, AlertTriangle, Activity, Layers, Cpu, Camera, Film, Radio, Sparkles } from "lucide-react";
import { Detection, ZoneSummary } from "@/lib/types";
import { InputMode } from "./InputModeSelector";
import styles from "./StatsBar.module.css";
import { ModelStatus } from "@/hooks/useModelStatus";
import { useGroqStatus } from "@/hooks/useGroqStatus";

interface Props {
  detections: Detection[];
  zones: ZoneSummary[];
  healthScore: number;
  inputMode: InputMode;
  modelStatus: ModelStatus;
}

const MODE_ICONS: Record<InputMode, React.ReactNode> = {
  image: <Camera size={14} />,
  video: <Film size={14} />,
  live:  <Radio size={14} />,
};

const MODE_LABELS: Record<InputMode, string> = {
  image: "IMAGE",
  video: "VIDEO",
  live:  "LIVE UAV",
};

export default function StatsBar({ detections, zones, healthScore, inputMode, modelStatus }: Props) {
  const groqStatus = useGroqStatus();
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
  const hsColor    = healthScore >= 70 ? "#10B981" : healthScore >= 40 ? "#F59E0B" : "#EF4444";
  const modelColor = modelStatus.ready
    ? (modelStatus.mock_mode ? "#3B82F6" : "#10B981")
    : "#EF4444";

  const stats = [
    { icon: <Activity size={16} color="#38BDF8"/>,       label: "TOTAL DETECTIONS", value: detections.length.toString(), color: "#38BDF8"  },
    { icon: <AlertTriangle size={16} color="#EF4444"/>,  label: "DISEASED ALERTS",  value: diseased.length.toString(),   color: "#EF4444"  },
    { icon: <Layers size={16} color="#3B82F6"/>,         label: "ZONES ACTIVE",     value: `${zonesActive} / ${zones.length}`, color: "#3B82F6" },
    { icon: <Shield size={16} color={hsColor}/>,         label: "HEALTH SCORE",     value: `${healthScore.toFixed(1)}%`, color: hsColor    },
  ];

  return (
    <div className={styles.bar}>
      {stats.map((s) => (
        <React.Fragment key={s.label}>
          <div className={styles.statBlock}>
            {s.icon}
            <div className={styles.statContent}>
              <span className={styles.statLabel}>{s.label}</span>
              <span className={styles.statValue} style={{ color: s.color }}>{s.value}</span>
            </div>
          </div>
          <div className={styles.divider}/>
        </React.Fragment>
      ))}

      {/* Dominant disease */}
      <div className={styles.statBlock}>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>DOMINANT DISEASE</span>
          <span className={styles.statValue} style={{ color: "#38BDF8", fontSize: "11px" }}>
            {dominant.replace(/_/g," ").toUpperCase()}
          </span>
        </div>
      </div>

      <div className={styles.divider}/>

      {/* Input mode indicator */}
      <div className={styles.statBlock} style={{ flex: "none", paddingRight: 0 }}>
        <span style={{ color: "#38BDF8" }}>{MODE_ICONS[inputMode]}</span>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>INPUT MODE</span>
          <span className={styles.statValue} style={{ color: "#38BDF8", fontSize: "11px" }}>
            {MODE_LABELS[inputMode]}
          </span>
        </div>
      </div>

      <div className={styles.divider}/>

      {/* Model status indicator */}
      <div className={styles.statBlock} style={{ flex: "none" }}>
        <Cpu size={16} color={modelColor}/>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>
            PARENT MODEL ({modelStatus.device?.toUpperCase() || "CPU"})
          </span>
          <span className={styles.statValue} style={{ color: modelColor, fontSize: "11px" }}>
            {modelStatus.ready
              ? (modelStatus.mock_mode ? "MOCK MODE" : `READY (${modelStatus.model_task?.toUpperCase()})`)
              : "LOADING…"}
          </span>
        </div>
      </div>

      <div className={styles.divider}/>

      {/* AI LLM Reasoning indicator */}
      <div className={styles.statBlock} style={{ flex: "none" }} title={groqStatus.configured ? `VLM: ${groqStatus.vlm_model} | Report: ${groqStatus.report_model}` : "API Key Not Set"}>
        <Sparkles size={16} color={groqStatus.configured ? "#10B981" : "#FBBF24"}/>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>
            AI LLM REASONING
          </span>
          <span className={styles.statValue} style={{ color: groqStatus.configured ? "#34D399" : "#FBBF24", fontSize: "11px" }}>
            {groqStatus.configured
              ? `READY (${groqStatus.vlm_model?.split("/")[1] || "QWEN3.6"})`
              : "KEY REQUIRED"}
          </span>
        </div>
      </div>
    </div>
  );
}
