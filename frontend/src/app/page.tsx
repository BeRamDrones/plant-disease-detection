"use client";
import React, { useState, useCallback, useMemo } from "react";
import MissionHeader from "@/components/MissionHeader";
import CameraFeed from "@/components/CameraFeed";
import DetectionPanel from "@/components/DetectionPanel";
import ZoneMap from "@/components/ZoneMap";
import StatsBar from "@/components/StatsBar";
import CompleteMissionButton from "@/components/CompleteMissionButton";
import ModelGate from "@/components/ModelGate";
import InputModeSelector, { InputMode } from "@/components/InputModeSelector";
import { useMissionDetections } from "@/hooks/useMissionDetections";
import { useModelStatus } from "@/hooks/useModelStatus";
import { useDetections, RawDetection } from "@/hooks/useDetections";
import { generateMissionSummary } from "@/lib/mockData";
import { diseaseColor, severityLabel } from "@/lib/types";
import {
  RotateCcw, Sliders, Cpu, Database, Info, Search, Filter, Download,
  LayoutDashboard, Radio, Map, BarChart2, Settings,
} from "lucide-react";
import styles from "./page.module.css";

// ── Simulated drone telemetry with subtle drift ───────────────────────────────
function useTelemetry() {
  const [alt,   setAlt]   = React.useState(85.4);
  const [speed, setSpeed] = React.useState(12.3);
  const [bat,   setBat]   = React.useState(78);
  const [sig,   setSig]   = React.useState(92);
  const [lat,   setLat]   = React.useState(21.1455);
  const [lon,   setLon]   = React.useState(79.0882);

  React.useEffect(() => {
    const t = setInterval(() => {
      setAlt  (v => +(v + (Math.random()-0.5)*0.3).toFixed(1));
      setSpeed(v => +(v + (Math.random()-0.5)*0.4).toFixed(1));
      setBat  (v => Math.max(5, +(v - 0.015).toFixed(1)));
      setSig  (v => Math.min(100, Math.max(60, v + (Math.random()-0.5)*2)));
      setLat  (v => +(v + (Math.random()-0.5)*0.0001).toFixed(5));
      setLon  (v => +(v + (Math.random()-0.5)*0.0001).toFixed(5));
    }, 1500);
    return () => clearInterval(t);
  }, []);

  return { alt, speed, bat, sig, lat, lon };
}

// ── Nav items ─────────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: "dashboard", icon: <LayoutDashboard size={18} />, label: "DASH"   },
  { id: "stream",    icon: <Radio size={18} />,           label: "STREAM" },
  { id: "map",       icon: <Map size={18} />,             label: "MAP"    },
  { id: "analytics", icon: <BarChart2 size={18} />,       label: "DATA"   },
  { id: "settings",  icon: <Settings size={18} />,        label: "CFG"    },
] as const;

// ─────────────────────────────────────────────────────────────────────────────
export default function MissionDashboard() {
  const modelStatus = useModelStatus();
  const { mission, elapsed } = useMissionDetections();
  const { detections, addDetections, clearDetections, totalScans } = useDetections();
  const { alt, speed, bat, sig, lat, lon } = useTelemetry();
  const summary = generateMissionSummary(detections, mission);

  const [activeNav, setActiveNav] = useState<string>("dashboard");
  const [inputMode, setInputMode] = useState<InputMode>("live");
  // Tracks whether the live UAV camera is actively streaming
  const [liveCamera, setLiveCamera] = useState(false);

  // ── Search & Filter State for DATA View ──
  const [searchQuery, setSearchQuery] = useState("");
  const [classFilter, setClassFilter] = useState<"all" | "diseased" | "healthy">("all");

  // ── Config State for CFG View ──
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.90);
  const [captureRate, setCaptureRate] = useState(1.0);

  // ── Filtered Detections for Data table ──
  const filteredDetections = useMemo(() => {
    return detections.filter(d => {
      const matchesSearch = d.detected_class.toLowerCase().includes(searchQuery.toLowerCase());
      const isHealthy     = d.detected_class.toLowerCase() === "healthy";
      const matchesFilter =
        classFilter === "all" ||
        (classFilter === "healthy" && isHealthy) ||
        (classFilter === "diseased" && !isHealthy);
      return matchesSearch && matchesFilter;
    });
  }, [detections, searchQuery, classFilter]);

  // Stable refs for lat/lon so handleDetections doesn't recreate every telemetry tick
  const latRef = React.useRef(lat);
  const lonRef = React.useRef(lon);
  React.useEffect(() => { latRef.current = lat; }, [lat]);
  React.useEffect(() => { lonRef.current = lon; }, [lon]);

  // Handler for incoming detections
  const handleDetections = useCallback((raws: RawDetection[]) => {
    // Client-side confidence filter based on slider value
    const filtered = raws.filter(r => r.confidence_score >= confidenceThreshold);
    addDetections(filtered, latRef.current, lonRef.current);
  }, [addDetections, confidenceThreshold]);

  // Handler for live camera active state changes
  const handleCameraActive = useCallback((active: boolean) => {
    setLiveCamera(active);
  }, []);

  // Derived: is the camera considered "off" for the purposes of DetectionPanel?
  const cameraOff = inputMode === "live" && !liveCamera;

  // Navigate & offset helper
  const navIndex = {
    dashboard: 0,
    stream:    1,
    map:       2,
    analytics: 3,
    settings:  4,
  }[activeNav] ?? 0;

  // Export CSV helper
  const exportCSV = () => {
    if (detections.length === 0) return;
    const headers = "ID,Timestamp,Class,Confidence,Lat,Lon,Model\n";
    const rows = detections.map(d => 
      `"${d.id}","${d.detected_at}","${d.detected_class}",${d.confidence_score},${d.lat},${d.lon},"${d.model_version}"`
    ).join("\n");
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `Jatayu_Mission_${mission.mission_id}_Detections.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={styles.root}>
      {/* ── Model gate overlay ── */}
      <ModelGate status={modelStatus} />

      {/* ── Top nav ── */}
      <MissionHeader
        mission={mission}
        elapsed={elapsed}
        signalStrength={Math.round(sig)}
        battery={Math.round(bat)}
        modelStatus={modelStatus}
        altitude={alt}
        speed={speed}
      />

      {/* ── Main layout ── */}
      <div className={styles.body}>

        {/* LEFT: vertical nav sidebar */}
        <nav className={styles.sidebar}>
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`${styles.navBtn} ${activeNav === item.id ? styles.navActive : ""}`}
              onClick={() => setActiveNav(item.id)}
              title={item.label}
            >
              {item.icon}
              <span className={styles.navLabel}>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* WORKSPACE: Sliding track container */}
        <div className={styles.workspace}>
          <div 
            className={styles.sliderTrack}
            style={{ transform: `translateX(-${navIndex * 20}%)` }}
          >
            
            {/* SLIDE 0: Dashboard (DASH) */}
            <div className={styles.slide}>
              <div className={styles.dashLayout}>
                {/* Center: camera feed */}
                <div className={styles.mainCol}>
                  <div className={styles.modeStrip}>
                    <InputModeSelector
                      mode={inputMode}
                      onModeChange={mode => {
                        setInputMode(mode);
                        clearDetections();
                        // Reset camera state when leaving live mode
                        if (mode !== "live") setLiveCamera(false);
                      }}
                      modelReady={modelStatus.ready}
                    />
                    <div className={styles.ctrlGroup}>
                      <div className={styles.detChips}>
                        <span className={styles.chip} style={{ color:"#00d4ff", borderColor:"rgba(0,212,255,0.25)", background:"rgba(0,212,255,0.05)" }}>
                          {detections.length} CROPS CLASSIFIED
                        </span>
                        {totalScans > 0 && (
                          <span className={styles.chip} style={{ color:"#8b5cf6", borderColor:"rgba(139,92,246,0.25)", background:"rgba(139,92,246,0.05)" }}>
                            {totalScans} SCANS
                          </span>
                        )}
                        <span className={styles.chip} style={{ color:"#f59e0b", borderColor:"rgba(245,158,11,0.25)", background:"rgba(245,158,11,0.05)" }} title="Parent model classifies crop species; child disease specialist models standby">
                          CHILD MODELS: STANDBY
                        </span>
                      </div>
                      <div className={styles.ctrlDivider}/>
                      <button
                        className={styles.ctrlBtn}
                        onClick={clearDetections}
                        title="Clear all detections"
                        disabled={!modelStatus.ready || detections.length === 0}
                      >
                        <RotateCcw size={11}/>
                        <span>CLEAR</span>
                      </button>
                    </div>
                  </div>
                  <div className={styles.feedWrap}>
                    <CameraFeed
                      altitude={alt}
                      speed={speed}
                      lat={lat}
                      lon={lon}
                      mode={inputMode}
                      modelReady={modelStatus.ready}
                      onDetections={handleDetections}
                      onCameraActive={handleCameraActive}
                      scanInterval={captureRate}
                    />
                  </div>
                </div>
                {/* Detections column */}
                <div className={styles.detectCol}>
                  <DetectionPanel detections={detections} modelReady={modelStatus.ready} totalScans={totalScans} cameraOff={cameraOff}/>
                </div>
                {/* Telemetry and Complete panel */}
                <div className={styles.rightCol}>
                  <ZoneMap zones={summary.zones_breakdown} detections={detections} />
                  <div className={styles.healthCard}>
                    <div className={styles.healthHeader}>
                      <span className={styles.healthLabel}>MISSION HEALTH SCORE</span>
                      <span className={styles.healthPct} style={{
                        color: summary.health_score >= 70 ? "#10b981" : summary.health_score >= 40 ? "#f59e0b" : "#ef4444"
                      }}>
                        {summary.health_score.toFixed(1)}%
                      </span>
                    </div>
                    <div className={styles.healthBar}>
                      <div className={styles.healthFill} style={{
                        width: `${summary.health_score}%`,
                        background: summary.health_score >= 70 ? "#10b981" : summary.health_score >= 40 ? "#f59e0b" : "#ef4444",
                      }}/>
                      <div className={styles.healthShimmer}/>
                    </div>
                  </div>
                  <div className={styles.zoneList}>
                    <div className={styles.zoneListHeader}>ZONE STATUS</div>
                    <div className={styles.zoneItems}>
                      {summary.zones_breakdown
                        .filter(z => z.detection_count > 0)
                        .sort((a,b) => b.detection_count - a.detection_count)
                        .slice(0,6)
                        .map(z => (
                          <div key={z.zone_id} className={styles.zoneItem}>
                            <span className={styles.zoneItemLabel}>{z.zone_label}</span>
                            <span className={styles.zoneItemClass}>
                              {(z.dominant_class ?? "—").toUpperCase()}
                            </span>
                            <span className={styles.zoneItemCount}>{z.detection_count}</span>
                          </div>
                        ))}
                      {summary.zones_breakdown.filter(z => z.detection_count > 0).length === 0 && (
                        <div className={styles.noZones}>No detections yet — submit an image or scan</div>
                      )}
                    </div>
                  </div>
                  <CompleteMissionButton mission={mission} detections={detections} elapsed={elapsed}/>
                </div>
              </div>
            </div>

            {/* SLIDE 1: Fullscreen Feed (STREAM) */}
            <div className={styles.slide}>
              <div className={styles.streamLayout}>
                <div className={styles.mainCol}>
                  <div className={styles.feedWrap}>
                    <CameraFeed
                      altitude={alt}
                      speed={speed}
                      lat={lat}
                      lon={lon}
                      mode={inputMode}
                      modelReady={modelStatus.ready}
                      onDetections={handleDetections}
                      onCameraActive={handleCameraActive}
                      scanInterval={captureRate}
                    />
                  </div>
                </div>
                <div className={styles.detectCol}>
                  <DetectionPanel detections={detections} modelReady={modelStatus.ready} totalScans={totalScans} cameraOff={cameraOff}/>
                </div>
              </div>
            </div>

            {/* SLIDE 2: Fullscreen Map (MAP) */}
            <div className={styles.slide}>
              <div className={styles.mapLayout}>
                <div className={styles.mapContainer}>
                  <ZoneMap zones={summary.zones_breakdown} detections={detections} />
                </div>
                <div className={styles.mapSidebar}>
                  <div className={styles.healthCard}>
                    <div className={styles.healthHeader}>
                      <span className={styles.healthLabel}>CURRENT ZONE DENSITY</span>
                      <span className={styles.healthPct} style={{ color: "#06b6d4" }}>
                        {detections.length} PIN(S)
                      </span>
                    </div>
                  </div>
                  <div className={styles.zoneList} style={{ flex: 1 }}>
                    <div className={styles.zoneListHeader}>DETECTION COORDINATES</div>
                    <div className={styles.zoneItems} style={{ maxHeight: "calc(100vh - 240px)", overflowY: "auto" }}>
                      {detections.slice(0, 15).map((d) => (
                        <div key={d.id} className={styles.zoneItem}>
                          <span 
                            className={styles.zoneItemClass} 
                            style={{ color: diseaseColor(d.detected_class) }}
                          >
                            {d.detected_class.toUpperCase()}
                          </span>
                          <span className={styles.zoneItemCount} style={{ fontFamily: "monospace", fontSize: "9px" }}>
                            {d.lat.toFixed(4)}, {d.lon.toFixed(4)}
                          </span>
                        </div>
                      ))}
                      {detections.length === 0 && (
                        <div className={styles.noZones}>No pins placed on the map yet</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* SLIDE 3: Log Data Table (DATA) */}
            <div className={styles.slide}>
              <div className={styles.dataLayout}>
                <div className={styles.dataHeader}>
                  <span className={styles.dataTitle}>DETECTION RECORDS LOG</span>
                  <div className={styles.dataActions}>
                    <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                      <Search size={12} color="#475569" style={{ position: "absolute", left: "8px" }}/>
                      <input
                        className={styles.searchInput}
                        placeholder="Search class..."
                        style={{ paddingLeft: "26px" }}
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                      />
                    </div>
                    <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                      <Filter size={12} color="#475569" style={{ position: "absolute", left: "8px" }}/>
                      <select
                        className={styles.selectInput}
                        style={{ paddingLeft: "26px" }}
                        value={classFilter}
                        onChange={e => setClassFilter(e.target.value as "all" | "diseased" | "healthy")}
                      >
                        <option value="all">ALL CLASSES</option>
                        <option value="diseased">DISEASED ONLY</option>
                        <option value="healthy">HEALTHY ONLY</option>
                      </select>
                    </div>
                    <button 
                      className={styles.ctrlBtn} 
                      onClick={exportCSV}
                      disabled={detections.length === 0}
                    >
                      <Download size={11}/>
                      <span>EXPORT CSV</span>
                    </button>
                  </div>
                </div>

                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Timestamp</th>
                        <th>Class</th>
                        <th>Type</th>
                        <th>Confidence</th>
                        <th>GPS Coordinates</th>
                        <th>Model version</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDetections.map((d) => (
                        <tr key={d.id}>
                          <td>{d.id}</td>
                          <td className={styles.tableTime}>{new Date(d.detected_at).toLocaleTimeString()}</td>
                          <td 
                            className={styles.tableClass} 
                            style={{ color: diseaseColor(d.detected_class) }}
                          >
                            {d.detected_class.toUpperCase()}
                          </td>
                          <td>
                            <span style={{ 
                              color: d.detected_class === "healthy" ? "#10b981" : "#ef4444",
                              fontSize: "9px",
                              fontFamily: "var(--font-hud)"
                            }}>
                              {severityLabel(d.detected_class)}
                            </span>
                          </td>
                          <td className={styles.tableConf}>{(d.confidence_score * 100).toFixed(1)}%</td>
                          <td className={styles.tableGps}>{d.lat.toFixed(5)}°N, {d.lon.toFixed(5)}°E</td>
                          <td>{d.model_version}</td>
                        </tr>
                      ))}
                      {filteredDetections.length === 0 && (
                        <tr>
                          <td colSpan={7} className={styles.noDataText}>
                            No detection logs match current search filters
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* SLIDE 4: Model Configuration Settings (CFG) */}
            <div className={styles.slide}>
              <div className={styles.configLayout}>
                {/* Settings Panel */}
                <div className={styles.configCard}>
                  <div className={styles.configHeader}>
                    <span className={styles.configTitle}>INFERENCE PARAMETERS</span>
                  </div>
                  <div className={styles.settingRow}>
                    <div className={styles.settingLabelWrap}>
                      <span className={styles.settingLabel}>CONFIDENCE FILTER THRESHOLD</span>
                      <span className={styles.settingValue}>{confidenceThreshold.toFixed(2)}</span>
                    </div>
                    <input
                      type="range"
                      min="0.05"
                      max="0.95"
                      step="0.05"
                      className={styles.sliderInput}
                      value={confidenceThreshold}
                      onChange={e => setConfidenceThreshold(parseFloat(e.target.value))}
                    />
                    <span style={{ fontSize: "9px", color: "var(--text-muted)", marginTop: "2px" }}>
                      Frames containing detections below this value will be automatically ignored.
                    </span>
                  </div>
                  <div className={styles.settingRow}>
                    <div className={styles.settingLabelWrap}>
                      <span className={styles.settingLabel}>LIVE UAV AUTO-SCAN RATE</span>
                      <span className={styles.settingValue}>{captureRate.toFixed(1)}s</span>
                    </div>
                    <input
                      type="range"
                      min="1.0"
                      max="10.0"
                      step="0.5"
                      className={styles.sliderInput}
                      value={captureRate}
                      onChange={e => setCaptureRate(parseFloat(e.target.value))}
                    />
                    <span style={{ fontSize: "9px", color: "var(--text-muted)", marginTop: "2px" }}>
                      Interval rate at which the live stream is processed for disease discovery.
                    </span>
                  </div>
                </div>

                {/* System Specs and Diagnostics */}
                <div className={styles.configCard}>
                  <div className={styles.configHeader}>
                    <span className={styles.configTitle}>HARDWARE & ENVIRONMENT DIAGNOSTICS</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    <div className={styles.infoField}>
                      <span className={styles.infoLabel}>INFERENCE ENGINE</span>
                      <span className={styles.infoValue}>ULTRALYTICS YOLOv8</span>
                    </div>
                    <div className={styles.infoField}>
                      <span className={styles.infoLabel}>DEVICE TYPE</span>
                      <span className={styles.infoValue} style={{ color: modelStatus.device?.includes("cuda") ? "#10b981" : "#f59e0b" }}>
                        {modelStatus.device?.toUpperCase() || "CPU"}
                      </span>
                    </div>
                    <div className={styles.infoField}>
                      <span className={styles.infoLabel}>PARENT MODEL FILE</span>
                      <span className={styles.infoValue}>{modelStatus.model_name}</span>
                    </div>
                    <div className={styles.infoField}>
                      <span className={styles.infoLabel}>MODEL FUNCTION</span>
                      <span className={styles.infoValue}>{modelStatus.model_task?.toUpperCase() || "CLASSIFICATION"}</span>
                    </div>
                    <div className={styles.infoField}>
                      <span className={styles.infoLabel}>BACKEND ENDPOINT</span>
                      <span className={styles.infoValue}>http://localhost:8000</span>
                    </div>
                  </div>
                  <div className={styles.configHeader} style={{ marginTop: "10px" }}>
                    <span className={styles.configTitle}>REAL-TIME HARDWARE CONSOLE</span>
                  </div>
                  <div className={styles.techLogs}>
                    {`[SYS] Initializing hardware monitors...\n` +
                     `[Device] GPU detected → ${modelStatus.device || "cpu"}\n` +
                     `[YOLO] YOLO best.pt loaded successfully.\n` +
                     `[YOLO] Task: ${modelStatus.model_task || "classify"} | Device: ${modelStatus.device || "cpu"}\n` +
                     `[Server] FastAPI routing active on port 8000.\n` +
                     `[Status] Ready to accept image/video streams.\n` +
                     `[Diagnostics] GPU temperature: 49°C | VRAM: 0.0GB / 8.0GB`}
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>

      </div>

      {/* ── Bottom stats bar ── */}
      <StatsBar
        detections={detections}
        zones={summary.zones_breakdown}
        healthScore={summary.health_score}
        inputMode={inputMode}
        modelStatus={modelStatus}
      />
    </div>
  );
}
