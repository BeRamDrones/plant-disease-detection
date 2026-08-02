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

// Plant classes from parent model (best.pt)
const CROP_CLASSES = new Set([
  "apple", "banana", "bittergourd", "blueberry", "cashew", "cassava",
  "castorbean", "coconut", "coffee", "coriander", "corn", "eggplant",
  "fennel", "grape", "guava", "jackfruit", "mango", "moringa", "neem",
  "notaleaf", "papaya", "peach", "pepperbell", "pomegranate", "potato",
  "raspberry", "sesame", "soybean", "sunflower", "sweetpotato", "tobacco",
  "tomato"
]);

export function diseaseColor(cls: string): string {
  const norm = cls.toLowerCase().replace(/_/g, "");
  if (norm === "healthy") return DISEASE_COLORS.healthy;
  if (CROP_CLASSES.has(norm)) {
    return norm === "notaleaf" ? "#ef4444" : "#00d4ff"; // Cyan for crops, Red for NotALeaf
  }
  
  // Find key in DISEASE_COLORS by normalized name
  const match = Object.keys(DISEASE_COLORS).find(
    k => k.toLowerCase().replace(/_/g, "") === norm
  );
  return match ? DISEASE_COLORS[match] : DISEASE_COLORS.unknown;
}

export function severityLabel(cls: string): string {
  const norm = cls.toLowerCase().replace(/_/g, "");
  if (norm === "healthy") return "HEALTHY";
  if (norm === "notaleaf") return "CRITICAL";
  if (CROP_CLASSES.has(norm)) return "CROP ID"; // Parent model classifies crop
  
  if (["rust", "blight", "bacterialwilt"].includes(norm)) return "CRITICAL";
  if (["leafspot", "anthracnose"].includes(norm)) return "HIGH";
  return "MODERATE";
}

