"use client";
import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  MapPin, Crosshair, Maximize2, Camera,
  Upload, Link2, RefreshCw, Play, Pause, Zap,
} from "lucide-react";
import { InputMode } from "./InputModeSelector";
import { RawDetection } from "@/hooks/useDetections";
import styles from "./CameraFeed.module.css";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Interval between auto-captured frames in Live UAV mode (ms)
const LIVE_CAPTURE_INTERVAL = 4000;

interface Props {
  altitude: number;
  speed: number;
  lat: number;
  lon: number;
  mode: InputMode;
  modelReady: boolean;
  /** Called with raw detection results from the backend inference endpoint */
  onDetections: (raws: RawDetection[]) => void;
  scanInterval?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared helper: post an image blob to the backend and return raw detections
// ─────────────────────────────────────────────────────────────────────────────
async function runInferenceOnBlob(
  blob: Blob,
  endpoint: "infer/image" | "infer/video-frame",
  filename = "frame.jpg"
): Promise<RawDetection[]> {
  const fd = new FormData();
  fd.append("file", blob, filename);
  const res = await fetch(`${BACKEND}/api/inference/${endpoint}`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return (data.detections ?? []) as RawDetection[];
}

// ─────────────────────────────────────────────────────────────────────────────
// IMAGE MODE
// ─────────────────────────────────────────────────────────────────────────────
function ImageMode({
  modelReady,
  onDetections,
}: {
  modelReady: boolean;
  onDetections: (raws: RawDetection[]) => void;
}) {
  const [preview,  setPreview]  = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [running,  setRunning]  = useState(false);
  const [result,   setResult]   = useState<{ count: number; cls: string[] } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setPreview(URL.createObjectURL(file));
    setResult(null);
    if (!modelReady) return;
    setRunning(true);
    try {
      const dets = await runInferenceOnBlob(file, "infer/image", file.name);
      onDetections(dets);
      setResult({
        count: dets.length,
        cls:   [...new Set(dets.map(d => d.detected_class))],
      });
    } catch {
      setResult({ count: -1, cls: [] }); // error sentinel
    } finally {
      setRunning(false);
    }
  };

  return (
    <div
      className={`${styles.dropZone} ${dragging ? styles.dragOver : ""}`}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => {
        e.preventDefault(); setDragging(false);
        const f = e.dataTransfer.files[0]; if (f) handleFile(f);
      }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef} type="file" accept="image/*" hidden
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
      />

      {preview ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={preview} alt="preview" className={styles.preview} />
      ) : (
        <div className={styles.dropPlaceholder}>
          <Upload size={32} color="rgba(0,212,255,0.3)" strokeWidth={1.2} />
          <span className={styles.dropTitle}>DROP IMAGE HERE</span>
          <span className={styles.dropSub}>or click to browse · PNG, JPG, WEBP</span>
        </div>
      )}

      {running && (
        <div className={styles.analysisOverlay}>
          <div className={styles.analysisSpin} />
          <span>RUNNING PARENT MODEL…</span>
        </div>
      )}

      {result !== null && (
        <div
          className={styles.resultChip}
          style={{ background: result.count < 0 ? "rgba(239,68,68,0.15)" : "rgba(10,14,26,0.9)" }}
          onClick={e => e.stopPropagation()}
        >
          {result.count < 0
            ? "⚠ Could not reach backend"
            : result.count === 0
              ? "✓ No detections in this image"
              : `✓ ${result.count} detection(s): ${result.cls.join(", ")}`
          }
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VIDEO MODE
// ─────────────────────────────────────────────────────────────────────────────
function VideoMode({
  modelReady,
  onDetections,
  scanInterval = 3,
}: {
  modelReady: boolean;
  onDetections: (raws: RawDetection[]) => void;
  scanInterval?: number;
}) {
  const videoRef   = useRef<HTMLVideoElement>(null);
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const timerRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const [src,       setSrc]       = useState<string | null>(null);
  const [scanning,  setScanning]  = useState(false);
  const [dragging,  setDragging]  = useState(false);
  const [scanCount, setScanCount] = useState(0);
  const [scanTotal, setScanTotal] = useState(0); // total detections across all frames
  const inputRef = useRef<HTMLInputElement>(null);
  const lastCapturedTimeRef = useRef<number>(-1);

  const handleFile = (file: File) => {
    setSrc(URL.createObjectURL(file));
    setScanCount(0);
    setScanTotal(0);
    lastCapturedTimeRef.current = -1;
    if (modelReady) {
      setScanning(true);
    }
  };

  const captureAndInfer = useCallback(async () => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.ended) return;

    // Avoid duplicate requests if video is paused on the same frame
    if (video.paused && video.currentTime === lastCapturedTimeRef.current) return;

    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 360;
    canvas.getContext("2d")?.drawImage(video, 0, 0);

    lastCapturedTimeRef.current = video.currentTime;

    canvas.toBlob(async blob => {
      if (!blob) return;
      try {
        const dets = await runInferenceOnBlob(blob, "infer/video-frame");
        onDetections(dets);
        setScanCount(c => c + 1);
        setScanTotal(t => t + dets.length);
      } catch { /* silent */ }
    }, "image/jpeg", 0.85);
  }, [onDetections]);

  // Reactive scan manager
  useEffect(() => {
    if (scanning && src && modelReady) {
      if (videoRef.current?.paused) {
        videoRef.current.play().catch(() => {});
      }
      captureAndInfer();
      timerRef.current = setInterval(captureAndInfer, scanInterval * 1000);
    } else {
      if (videoRef.current && !videoRef.current.paused) {
        videoRef.current.pause();
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [scanning, src, modelReady, captureAndInfer]);

  const toggleScan = () => {
    setScanning(s => !s);
  };

  const clearVideo = () => {
    setSrc(null);
    setScanning(false);
  };

  return (
    <div
      className={`${styles.videoMode} ${!src ? styles.dropZone : ""} ${dragging ? styles.dragOver : ""}`}
      onDragOver={e => {
        if (src) return;
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => {
        if (src) return;
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files[0];
        if (f) handleFile(f);
      }}
      onClick={() => {
        if (!src) inputRef.current?.click();
      }}
    >
      <input ref={inputRef} type="file" accept="video/*" hidden
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
      <canvas ref={canvasRef} hidden />

      {!src ? (
        <div className={styles.dropPlaceholder}>
          <Upload size={32} color="rgba(0,212,255,0.3)" strokeWidth={1.2} />
          <span className={styles.dropTitle}>DROP VIDEO HERE</span>
          <span className={styles.dropSub}>or click to browse · MP4, MOV, AVI, WEBM</span>
        </div>
      ) : (
        <div className={styles.videoPlayerContainer} onClick={e => e.stopPropagation()}>
          <video ref={videoRef} src={src} controls className={styles.videoPlayer} />
          <div className={styles.videoControls}>
            <button
              className={`${styles.scanBtn} ${scanning ? styles.scanActive : ""}`}
              onClick={toggleScan}
              disabled={!modelReady}
            >
              {scanning ? <Pause size={11} /> : <Play size={11} />}
              {scanning ? "STOP SCAN" : "START SCAN"}
            </button>
            {scanCount > 0 && (
              <span className={styles.scanCount}>
                {scanCount} FRAMES · {scanTotal} DETECTIONS
              </span>
            )}
            <button className={styles.clearBtn} onClick={clearVideo}>
              <RefreshCw size={10} /> CLEAR
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// LIVE UAV MODE
// ─────────────────────────────────────────────────────────────────────────────
function LiveUAVMode({
  altitude, speed, lat, lon, modelReady, onDetections, scanInterval = 4,
}: {
  altitude: number; speed: number; lat: number; lon: number;
  modelReady: boolean;
  onDetections: (raws: RawDetection[]) => void;
  scanInterval?: number;
}) {
  const videoRef    = useRef<HTMLVideoElement>(null);
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const wrapRef     = useRef<HTMLDivElement>(null);
  const captureRef  = useRef<ReturnType<typeof setInterval> | null>(null);

  const [camStatus,   setCamStatus]   = useState<"requesting"|"active"|"unavailable">("requesting");
  const [rtspUrl,     setRtspUrl]     = useState("");
  const [showRtsp,    setShowRtsp]    = useState(false);
  const [autoCapture, setAutoCapture] = useState(false);
  const [lastResult,  setLastResult]  = useState<string | null>(null);

  // Start webcam
  useEffect(() => {
    let stream: MediaStream | null = null;
    navigator.mediaDevices?.getUserMedia({ video: true })
      .then(s => { stream = s; if (videoRef.current) videoRef.current.srcObject = s; setCamStatus("active"); })
      .catch(() => setCamStatus("unavailable"));
    return () => {
      stream?.getTracks().forEach(t => t.stop());
      if (captureRef.current) clearInterval(captureRef.current);
    };
  }, []);

  // Capture a frame and send to backend
  const captureFrame = useCallback(async () => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !modelReady) return;
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 360;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(async blob => {
      if (!blob) return;
      try {
        const dets = await runInferenceOnBlob(blob, "infer/video-frame");
        onDetections(dets);
        setLastResult(
          dets.length > 0
            ? `${dets.length} detection(s): ${[...new Set(dets.map(d => d.detected_class))].join(", ")}`
            : "No detections in this frame"
        );
      } catch { setLastResult("Backend error"); }
    }, "image/jpeg", 0.85);
  }, [modelReady, onDetections]);

  // Toggle automatic frame capture
  const toggleAutoCapture = () => {
    if (autoCapture) {
      setAutoCapture(false);
      if (captureRef.current) { clearInterval(captureRef.current); captureRef.current = null; }
    } else {
      setAutoCapture(true);
      captureRef.current = setInterval(captureFrame, scanInterval * 1000);
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement && wrapRef.current) wrapRef.current.requestFullscreen();
    else document.exitFullscreen();
  };

  return (
    <div className={styles.wrap} ref={wrapRef}>
      <canvas ref={canvasRef} hidden />

      {/* Camera source */}
      {camStatus === "active" ? (
        <video ref={videoRef} autoPlay playsInline muted className={styles.video} />
      ) : (
        <div className={styles.placeholder}>
          <div className={styles.noise} />
          <div className={styles.noSignalText}>
            {camStatus === "requesting" ? (
              <><div className={styles.spinner} /><span>ESTABLISHING LINK…</span></>
            ) : (
              <>
                <Camera size={40} color="rgba(0,212,255,0.3)" />
                <span>NO CAMERA SIGNAL</span>
                <span className={styles.noSigSub}>Awaiting drone video feed</span>
              </>
            )}
          </div>
          {Array.from({length: 24}).map((_, i) => (
            <div key={i} className={styles.terrainDot} style={{
              left: `${5 + (i % 6) * 17}%`,
              top:  `${10 + Math.floor(i / 6) * 22}%`,
              animationDelay: `${i * 0.15}s`,
              opacity: 0.3 + (i % 3) * 0.15,
            }}/>
          ))}
        </div>
      )}

      {/* RTSP panel */}
      {showRtsp && (
        <div className={styles.rtspPanel}>
          <Link2 size={12} color="#00d4ff" />
          <input
            className={styles.rtspInput}
            placeholder="rtsp://drone-ip:554/stream"
            value={rtspUrl}
            onChange={e => setRtspUrl(e.target.value)}
          />
          <button className={styles.rtspConnect}>CONNECT</button>
        </div>
      )}

      {/* Last detection result badge */}
      {lastResult && (
        <div className={styles.liveResultBadge}>
          <Zap size={9} color="#00d4ff" />
          {lastResult}
        </div>
      )}

      {/* Scan line */}
      <div className={styles.scanLine} />

      {/* Corner brackets */}
      <div className={`${styles.corner} ${styles.tl}`} />
      <div className={`${styles.corner} ${styles.tr}`} />
      <div className={`${styles.corner} ${styles.bl}`} />
      <div className={`${styles.corner} ${styles.br}`} />

      {/* Center crosshair */}
      <div className={styles.crosshair}>
        <Crosshair size={32} color="rgba(0,212,255,0.5)" strokeWidth={0.8} />
      </div>

      {/* Top HUD */}
      <div className={styles.topHud}>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>REC</span>
          <span className={styles.recDot} />
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>CAM</span>
          <span className={styles.hudValue} style={{ color: camStatus === "active" ? "#22c55e" : "#ef4444" }}>
            {camStatus === "active" ? "LIVE" : "OFFLINE"}
          </span>
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>AI</span>
          <span className={styles.hudValue} style={{ color: autoCapture ? "#22c55e" : "#94a3b8" }}>
            {autoCapture ? "SCANNING" : "IDLE"}
          </span>
        </div>
        <div className={styles.spacer} />

        {/* AI scan toggle */}
        {modelReady && camStatus === "active" && (
          <button
            className={`${styles.fsBtn} ${autoCapture ? styles.fsBtnActive : ""}`}
            onClick={toggleAutoCapture}
            title={autoCapture ? "Stop AI frame capture" : "Start AI frame capture"}
          >
            <Zap size={13} color={autoCapture ? "#22c55e" : "#94a3b8"} />
          </button>
        )}

        {/* Manual capture */}
        {modelReady && camStatus === "active" && (
          <button className={styles.fsBtn} onClick={captureFrame} title="Capture & analyse frame now">
            <Camera size={13} color="#00d4ff" />
          </button>
        )}

        <button className={styles.fsBtn} onClick={() => setShowRtsp(v => !v)} title="RTSP URL">
          <Link2 size={13} color="#94a3b8" />
        </button>
        <button className={styles.fsBtn} onClick={toggleFullscreen} title="Fullscreen">
          <Maximize2 size={13} color="#94a3b8" />
        </button>
      </div>

      {/* Bottom HUD telemetry */}
      <div className={styles.bottomHud}>
        <div className={styles.hudTelRow}>
          <div className={styles.telBlock}>
            <span className={styles.hudLabel}>ALT</span>
            <span className={styles.hudBigVal}>{altitude.toFixed(1)}<span className={styles.hudUnit}>m</span></span>
          </div>
          <div className={styles.telBlock}>
            <span className={styles.hudLabel}>SPD</span>
            <span className={styles.hudBigVal}>{speed.toFixed(1)}<span className={styles.hudUnit}>m/s</span></span>
          </div>
          <div className={`${styles.telBlock} ${styles.gpsTel}`}>
            <MapPin size={10} color="#a855f7" />
            <span className={styles.hudLabel}>GPS</span>
            <span className={styles.gpsVal}>{lat.toFixed(4)}°N &nbsp;{lon.toFixed(4)}°E</span>
          </div>
          <div className={styles.telBlock}>
            <span className={styles.hudLabel}>HEADING</span>
            <span className={styles.hudBigVal}>247°<span className={styles.hudUnit}>SW</span></span>
          </div>
        </div>
      </div>

      <div className={styles.gridOverlay} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN EXPORT
// ─────────────────────────────────────────────────────────────────────────────
export default function CameraFeed({ altitude, speed, lat, lon, mode, modelReady, onDetections, scanInterval }: Props) {
  return (
    <div className={styles.container}>
      {mode === "image" && (
        <ImageMode modelReady={modelReady} onDetections={onDetections} />
      )}
      {mode === "video" && (
        <VideoMode modelReady={modelReady} onDetections={onDetections} scanInterval={scanInterval} />
      )}
      {mode === "live" && (
        <LiveUAVMode
          altitude={altitude} speed={speed} lat={lat} lon={lon}
          modelReady={modelReady}
          onDetections={onDetections}
          scanInterval={scanInterval}
        />
      )}
    </div>
  );
}
