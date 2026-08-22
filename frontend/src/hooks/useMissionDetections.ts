"use client";
import { useState, useEffect, useCallback } from "react";
import { MissionData } from "@/lib/types";

const DEMO_MISSION: MissionData = {
  mission_id:  1024,
  drone_id:    "AG-DRONE-001",
  phase:       "detection",
  status:      "in_progress",
  crop_class:  undefined,
  created_at:  new Date(Date.now() - 18 * 60_000).toISOString(),
  updated_at:  new Date().toISOString(),
};

export function useMissionDetections() {
  const [mission] = useState<MissionData>(DEMO_MISSION);
  const [elapsed, setElapsed] = useState(0);

  // Elapsed mission timer — always runs independently
  useEffect(() => {
    const t = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  return { mission, elapsed };
}

export function formatElapsed(s: number): string {
  const h   = Math.floor(s / 3600).toString().padStart(2, "0");
  const m   = Math.floor((s % 3600) / 60).toString().padStart(2, "0");
  const sec = (s % 60).toString().padStart(2, "0");
  return `${h}:${m}:${sec}`;
}
