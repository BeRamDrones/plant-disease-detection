// Types shared across the entire dashboard
export interface Detection {
  id: string;
  detected_class: string;
  confidence_score: number;
  lat: number;
  lon: number;
  zone_id: number | null;
  zone_label?: string;
  image_ref?: string;
  model_version: string;
  detected_at: string;
}

export interface ZoneSummary {
  zone_id: number;
  zone_label: string;
  dominant_class: string | null;
  detection_count: number;
  avg_confidence: number;
}

export interface MissionData {
  mission_id: number;
  drone_id: string;
  phase: "survey" | "detection";
  status: "scheduled" | "in_progress" | "completed" | "aborted";
  crop_class?: string;
  created_at: string;
  updated_at: string;
}

export interface MissionSummary {
  mission: MissionData;
  zones_breakdown: ZoneSummary[];
  health_score: number;
}

export const DISEASE_COLORS: Record<string, string> = {
  healthy:         "#22c55e",
  powdery_mildew:  "#f59e0b",
  rust:            "#ef4444",
  blight:          "#ef4444",
  leaf_spot:       "#f97316",
  mosaic_virus:    "#a855f7",
  bacterial_wilt:  "#ef4444",
  anthracnose:     "#f97316",
  downy_mildew:    "#eab308",
  unknown:         "#94a3b8",
};

export function diseaseColor(cls: string): string {
  return DISEASE_COLORS[cls] ?? DISEASE_COLORS.unknown;
}
export function severityLabel(cls: string): string {
  if (cls === "healthy") return "HEALTHY";
  if (["rust","blight","bacterial_wilt"].includes(cls)) return "CRITICAL";
  if (["leaf_spot","anthracnose"].includes(cls)) return "HIGH";
  return "MODERATE";
}
