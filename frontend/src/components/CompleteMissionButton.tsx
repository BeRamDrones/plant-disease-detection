"use client";
import React, { useState } from "react";
import { FileText, CheckCircle, Loader2, AlertTriangle } from "lucide-react";
import styles from "./CompleteMissionButton.module.css";
import { Detection, MissionData } from "@/lib/types";
import { generateMissionSummary } from "@/lib/mockData";
import { generateMissionPDF } from "@/lib/pdfReport";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Props { mission: MissionData; detections: Detection[]; elapsed: number; }

type State = "idle" | "generating" | "done" | "error";

export default function CompleteMissionButton({ mission, detections, elapsed }: Props) {
  const [state, setState] = useState<State>("idle");

  const handleClick = async () => {
    if (state !== "idle") return;
    setState("generating");
    try {
      const summary = generateMissionSummary(detections, mission);
      
      // Request AI Agronomic synthesis from backend (Google Gemini / Neural Engine)
      let aiData = null;
      try {
        const aiRes = await fetch(`${BACKEND}/api/missions/ai-report-summary`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mission_id: mission.mission_id,
            crop_class: mission.crop_class || detections[0]?.plant_class,
            health_score: summary.health_score,
            detections: detections.slice(0, 100),
            zones: summary.zones_breakdown,
          }),
        });
        if (aiRes.ok) {
          aiData = await aiRes.json();
        }
      } catch {
        /* Fallback seamlessly handled inside generateMissionPDF */
      }

      generateMissionPDF(summary, detections, elapsed, aiData);
      setState("done");
      setTimeout(() => setState("idle"), 4000);
    } catch (e) {
      console.error(e);
      setState("error");
      setTimeout(() => setState("idle"), 3000);
    }
  };

  const label = {
    idle:       "COMPLETE MISSION",
    generating: "GENERATING REPORT…",
    done:       "REPORT DOWNLOADED",
    error:      "GENERATION FAILED",
  }[state];

  const Icon = {
    idle:       FileText,
    generating: Loader2,
    done:       CheckCircle,
    error:      AlertTriangle,
  }[state];

  return (
    <button
      className={`${styles.btn} ${styles[state]}`}
      onClick={handleClick}
      disabled={state !== "idle"}
    >
      {/* Animated ring */}
      <span className={styles.ring}/>
      <span className={styles.ring2}/>
      <Icon
        size={16}
        className={state === "generating" ? styles.spinIcon : ""}
      />
      <span className={styles.label}>{label}</span>
      {state === "done" && (
        <span className={styles.subLabel}>PDF Saved to Downloads</span>
      )}
    </button>
  );
}
