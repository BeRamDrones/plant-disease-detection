import { Detection, MissionData, MissionSummary, ZoneSummary, getZoneFromCoords } from "./types";

const DISEASES = [
  "healthy","powdery_mildew","rust","blight",
  "leaf_spot","mosaic_virus","anthracnose","downy_mildew",
];
const ZONES = ["A1","A2","B1","B2","C1","C2","D1","D2"];

let _detectionCounter = 1;

export function generateDetection(missionId: number): Detection {
  const cls   = DISEASES[Math.floor(Math.random() * DISEASES.length)];
  const zoneIdx = Math.floor(Math.random() * ZONES.length);
  const id    = `det-${_detectionCounter++}`;
  const lat   = 21.145 + (Math.random() - 0.5) * 0.005;
  const lon   = 79.088 + (Math.random() - 0.5) * 0.005;
  const zone  = getZoneFromCoords(lat, lon);
  return {
    id,
    detected_class:   cls,
    confidence_score: 0.70 + Math.random() * 0.29,
    lat,
    lon,
    zone_id:    zone.zone_id,
    zone_label: zone.zone_label,
    image_ref:  `/frames/${id}.jpg`,
    model_version: "jatayu_v1.2",
    detected_at: new Date().toISOString(),
  };
}

export function generateMissionSummary(
  detections: Detection[],
  mission: MissionData
): MissionSummary {
  // Defensive guard — detections may be undefined during SSR/HMR transitions
  const safeDetections = Array.isArray(detections) ? detections : [];
  const zoneMap: Record<string, Detection[]> = {};
  safeDetections.forEach(d => {
    const k = d.zone_label ?? getZoneFromCoords(d.lat, d.lon).zone_label;
    if (!zoneMap[k]) zoneMap[k] = [];
    zoneMap[k].push(d);
  });

  // Dynamically form zones ONLY for sectors where detections have been discovered at runtime
  const uniqueLabels = Object.keys(zoneMap);
  const zones_breakdown: ZoneSummary[] = uniqueLabels.map((label, idx) => {
    const dets = zoneMap[label];
    const counts: Record<string, number> = {};
    dets.forEach(d => { counts[d.detected_class] = (counts[d.detected_class] ?? 0) + 1; });
    const dominant = dets.length
      ? Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]
      : null;
    const avg_confidence = dets.length
      ? dets.reduce((s, d) => s + d.confidence_score, 0) / dets.length
      : 0;
    return {
      zone_id: idx + 1,
      zone_label: label,
      dominant_class: dominant,
      detection_count: dets.length,
      avg_confidence,
    };
  });

  const healthyZones = zones_breakdown.filter(z => !z.dominant_class || z.dominant_class === "healthy").length;
  const health_score = zones_breakdown.length ? (healthyZones / zones_breakdown.length) * 100 : 100;

  return { mission, zones_breakdown, health_score };
}
