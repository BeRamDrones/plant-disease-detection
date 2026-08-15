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
  rank?: number;        // classify model rank: 1 = top prediction, 2 = 2nd, etc.
  grid_zone?: string;   // image quadrant: Top-Left, Top-Right, etc.
  plant_class?: string;
  parent_confidence?: number;
  parent_model?: string;
  child_status?: string;
  vlm_verdict?: string;
  vlm_reasoning?: string;
  pathogen_name?: string;
  severity?: string;
  ai_audited?: boolean;
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
  healthy:         "#22C55E",
  powdery_mildew:  "#F59E0B",
  rust:            "#EF4444",
  blight:          "#EF4444",
  leaf_spot:       "#F59E0B",
  mosaic_virus:    "#F59E0B",
  bacterial_wilt:  "#EF4444",
  anthracnose:     "#F59E0B",
  downy_mildew:    "#F59E0B",
  unknown:         "#5E6D88",
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
  const norm = cls.toLowerCase().replace(/[\s_-]/g, "");
  if (norm.includes("healthy")) return DISEASE_COLORS.healthy;
  if (norm === "notaleaf") return "#EF4444";
  if (CROP_CLASSES.has(norm)) {
    return "#38BDF8"; // Sky teal for crop ID
  }
  
  if (["rust", "blight", "scab", "rot", "wilt", "measles", "gumming"].some(d => norm.includes(d))) {
    return "#EF4444"; // Red for critical diseases
  }
  if (["spot", "mildew", "virus", "anthracnose", "miner", "mold", "mosaic", "sigatoka"].some(d => norm.includes(d))) {
    return "#F59E0B"; // Amber for moderate/high diseases
  }
  
  const match = Object.keys(DISEASE_COLORS).find(
    k => norm.includes(k.toLowerCase().replace(/[\s_-]/g, ""))
  );
  return match ? DISEASE_COLORS[match] : "#F59E0B";
}

export function severityLabel(cls: string): string {
  const norm = cls.toLowerCase().replace(/[\s_-]/g, "");
  if (norm.includes("healthy")) return "HEALTHY";
  if (norm === "notaleaf") return "NOT A LEAF";
  if (CROP_CLASSES.has(norm)) return "CROP ID";
  
  if (["rust", "blight", "bacterialwilt", "scab", "rot", "measles", "gumming"].some(d => norm.includes(d))) return "CRITICAL";
  if (["spot", "anthracnose", "virus", "mildew", "miner", "mold", "mosaic", "sigatoka"].some(d => norm.includes(d))) return "HIGH";
  return "MODERATE";
}

export function getTreatmentAdvisory(cls: string): { action: string; remedy: string } {
  const norm = cls.toLowerCase().replace(/[\s_-]/g, "");
  if (norm.includes("healthy")) {
    return {
      action: "Routine Surveillance & Optimal Foliage",
      remedy: "Foliage verified healthy. Continue scheduled UAV mission flights and irrigation cycles."
    };
  }
  if (norm.includes("scab")) {
    return {
      action: "Fungicide Spray & Pruning",
      remedy: "Apply protectant captan or difenoconazole spray. Remove infected leaves and improve canopy ventilation."
    };
  }
  if (norm.includes("rot")) {
    return {
      action: "Immediate Sector Sanitation",
      remedy: "Prune dead mummified fruit and infected cankers. Apply thiophanate-methyl or captan fungicide."
    };
  }
  if (norm.includes("powderymildew") || norm.includes("mildew")) {
    return {
      action: "Targeted Fungicide Spray",
      remedy: "Apply sulfur-based or potassium bicarbonate spray. Improve air circulation around canopy."
    };
  }
  if (norm.includes("rust")) {
    return {
      action: "Immediate Sector Isolation",
      remedy: "Apply copper hydroxide fungicide immediately. Avoid overhead watering to prevent spore spread."
    };
  }
  if (norm.includes("blight")) {
    return {
      action: "Emergency Drone Payload Treatment",
      remedy: "High risk of rapid crop loss. Deploy systemic fungicide (Mancozeb/Chlorothalonil) and prune infected stems."
    };
  }
  if (norm.includes("spot")) {
    return {
      action: "Canopy Pruning & Bio-Fungicide",
      remedy: "Apply Bacillus subtilis or neem oil extract. Remove fallen foliage from zone perimeter."
    };
  }
  if (norm.includes("virus") || norm.includes("mosaic")) {
    return {
      action: "Vector Control (Aphids/Whiteflies)",
      remedy: "Viral infection—no direct chemical cure. Destroy infected hosts and control insect vectors."
    };
  }
  if (norm.includes("anthracnose")) {
    return {
      action: "Foliar Spray & Soil Aeration",
      remedy: "Apply copper-based fungicides during early morning. Ensure proper soil drainage."
    };
  }
  if (norm.includes("miner")) {
    return {
      action: "Insecticide / Parasitic Wasps",
      remedy: "Apply abamectin or spinosad. Introduce Diglyphus isaea biological control agents."
    };
  }
  if (norm === "notaleaf") {
    return {
      action: "Recalibrate Drone Altitude",
      remedy: "Non-crop geometry detected in scan payload. Adjust gimbal tilt or target coordinates."
    };
  }
  if (CROP_CLASSES.has(norm)) {
    return {
      action: "Species Classification Verified",
      remedy: `Identified crop species: ${cls.toUpperCase()}. Proceed to child model disease specialist phase.`
    };
  }
  return {
    action: "Agronomic Inspection Recommended",
    remedy: "Anomalous foliage patterns observed. Conduct manual ground truth sample validation."
  };
}

const COLS = ["A", "B", "C", "D"];
const ROWS = ["1", "2"];
const LAT_RANGE = 0.004;
const LON_RANGE = 0.004;
const CENTER_LAT = 21.1455;
const CENTER_LON = 79.0882;

export function getZoneFromCoords(lat: number, lon: number): { zone_id: number; zone_label: string } {
  const normLon = Math.min(1, Math.max(0, (lon - (CENTER_LON - LON_RANGE / 2)) / LON_RANGE));
  const normLat = Math.min(1, Math.max(0, (lat - (CENTER_LAT - LAT_RANGE / 2)) / LAT_RANGE));

  const colIdx = Math.min(3, Math.floor(normLon * 4));
  const rowIdx = Math.min(1, Math.floor(normLat * 2));

  const label = `${COLS[colIdx]}${ROWS[rowIdx]}`;
  const zoneIndexMap: Record<string, number> = {
    A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6, D1: 7, D2: 8
  };

  return {
    zone_id: zoneIndexMap[label] ?? 1,
    zone_label: label,
  };
}
