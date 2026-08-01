"use client";
import { useState, useEffect, useCallback } from "react";
import { Detection, MissionData } from "@/lib/types";
import { generateDetection } from "@/lib/mockData";

const DEMO_MISSION: MissionData = {
  mission_id:  1024,
  drone_id:    "AG-DRONE-001",
  phase:       "detection",
  status:      "in_progress",
  crop_class:  "wheat",
  created_at:  new Date(Date.now() - 18 * 60_000).toISOString(),
  updated_at:  new Date().toISOString(),
};

export function useMissionDetections() {
  const [mission]       = useState<MissionData>(DEMO_MISSION);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [elapsed, setElapsed]       = useState(0);
  const [paused,  setPaused]        = useState(false);

  // Elapsed timer
  useEffect(() => {
    const t = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  // Streaming detections every 2.5 s
  useEffect(() => {
    if (paused) return;
    const t = setInterval(() => {
      setDetections(prev => {
        const next = [generateDetection(mission.mission_id), ...prev];
        return next.slice(0, 120); // keep last 120
      });
    }, 2500);
    return () => clearInterval(t);
  }, [paused, mission.mission_id]);

  const reset = useCallback(() => setDetections([]), []);

  return { mission, detections, elapsed, paused, setPaused, reset };
}

export function formatElapsed(s: number): string {
  const h = Math.floor(s / 3600).toString().padStart(2,"0");
  const m = Math.floor((s % 3600) / 60).toString().padStart(2,"0");
  const sec = (s % 60).toString().padStart(2,"0");
  return `${h}:${m}:${sec}`;
}
