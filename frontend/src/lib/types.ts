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
  healthy:         "#00F0FF",
  powdery_mildew:  "#3B82F6",
  rust:            "#FF2D95",
  blight:          "#FF2D95",
  leaf_spot:       "#3B82F6",
  mosaic_virus:    "#3B82F6",
  bacterial_wilt:  "#FF2D95",
  anthracnose:     "#3B82F6",
  downy_mildew:    "#3B82F6",
  unknown:         "rgba(255,255,255,0.45)",
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
    return norm === "notaleaf" ? "#FF2D95" : "#00F0FF"; // Cyan for crops, Pink for NotALeaf alert
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
  if (norm === "notaleaf") return "NOT A LEAF";
  if (CROP_CLASSES.has(norm)) return "CROP ID"; // Parent model classifies crop
  
  if (["rust", "blight", "bacterialwilt"].includes(norm)) return "CRITICAL";
  if (["leafspot", "anthracnose"].includes(norm)) return "HIGH";
  return "MODERATE";
}

export function getTreatmentAdvisory(cls: string): { action: string; remedy: string } {
  const norm = cls.toLowerCase().replace(/_/g, "");
  if (norm === "healthy") {
    return {
      action: "Routine Monitoring",
      remedy: "Optimal foliage health. Continue regular irrigation and drone surveillance schedules."
    };
  }
  if (norm === "powderymildew") {
    return {
      action: "Targeted Fungicide Spray",
      remedy: "Apply sulfur-based or potassium bicarbonate spray. Improve air circulation around canopy."
    };
  }
  if (norm === "rust") {
    return {
      action: "Immediate Sector Isolation",
      remedy: "Apply copper hydroxide fungicide immediately. Avoid overhead watering to prevent spore spread."
    };
  }
  if (norm === "blight") {
    return {
      action: "Emergency Drone Payload Treatment",
      remedy: "High risk of rapid crop loss. Deploy systemic fungicide (Mancozeb/Chlorothalonil) and prune infected stems."
    };
  }
  if (norm === "leafspot") {
    return {
      action: "Canopy Pruning & Bio-Fungicide",
      remedy: "Apply Bacillus subtilis or neem oil extract. Remove fallen foliage from zone perimeter."
    };
  }
  if (norm === "mosaicvirus") {
    return {
      action: "Vector Vector Control (Aphids/Whiteflies)",
      remedy: "Viral infection—no direct chemical cure. Destroy infected hosts and control aphid vectors."
    };
  }
  if (norm === "anthracnose") {
    return {
      action: "Foliar Spray & Soil Aeration",
      remedy: "Apply copper-based fungicides during early morning. Ensure proper soil drainage."
    };
  }
  if (norm === "downymildew") {
    return {
      action: "Humidity Reduction & Spray",
      remedy: "Apply systemic oomycete fungicide (Fosetyl-Al). Reduce irrigation frequency."
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

