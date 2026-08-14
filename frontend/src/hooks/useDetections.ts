"use client";
import { useState, useCallback } from "react";
import { Detection, getZoneFromCoords } from "@/lib/types";

/**
 * Raw shape returned by /api/inference/infer/image and /api/inference/infer/video-frame
 * These come from the parent model (best.pt) running YOLO classification/detection.
 */
export interface RawDetection {
  detected_class: string;
  confidence_score: number;
  x_center?: number;
  y_center?: number;
  plant_class?: string;
  parent_confidence?: number;
  parent_model?: string;
  model_name?: string;
  child_status?: string;
  rank?: number;        // classification rank: 1 = top prediction
  grid_zone?: string;
}

let _counter = 1;

/** Maps a raw API detection to the shared Detection type used by the UI */
function mapDetection(raw: RawDetection, droneLat: number, droneLon: number): Detection {
  // Spread x/y offsets around the drone's current GPS position for map pins
  const latOffset = ((raw.x_center ?? 0.5) - 0.5) * 0.005;
  const lonOffset = ((raw.y_center ?? 0.5) - 0.5) * 0.005;

  const lat = +(droneLat + latOffset).toFixed(5);
  const lon = +(droneLon + lonOffset).toFixed(5);
  const zone = getZoneFromCoords(lat, lon);

  return {
    id:                `det-${_counter++}`,
    detected_class:    raw.detected_class,
    confidence_score:  raw.confidence_score,
    lat,
    lon,
    zone_id:           zone.zone_id,
    zone_label:        zone.zone_label,
    model_version:     raw.model_name ?? "best.pt",
    detected_at:       new Date().toISOString(),
    rank:              raw.rank,
    grid_zone:         raw.grid_zone,
    plant_class:       raw.plant_class,
    parent_confidence: raw.parent_confidence,
    parent_model:      raw.parent_model,
    child_status:      raw.child_status,
  };
}

interface UseDetectionsReturn {
  detections: Detection[];
  /** Call this with raw API results + current drone position to add real detections */
  addDetections: (raws: RawDetection[], droneLat: number, droneLon: number) => void;
  /** Clear all detections */
  clearDetections: () => void;
  totalScans: number;
}

/**
 * Manages real detections from the parent model.
 * ONLY populated by actual API responses — never generates random data.
 */
export function useDetections(): UseDetectionsReturn {
  const [detections, setDetections] = useState<Detection[]>([]);
  const [totalScans,  setTotalScans]  = useState(0);

  const addDetections = useCallback((raws: RawDetection[], droneLat: number, droneLon: number) => {
    // Always count this as a scan attempt — even if all results were confidence-filtered away
    setTotalScans(n => n + 1);
    if (!raws || raws.length === 0) return;
    const mapped = raws.map(r => mapDetection(r, droneLat, droneLon));
    setDetections(prev => [...mapped, ...prev].slice(0, 200)); // keep last 200
  }, []);

  const clearDetections = useCallback(() => {
    setDetections([]);
    setTotalScans(0);
  }, []);

  return { detections, addDetections, clearDetections, totalScans };
}
