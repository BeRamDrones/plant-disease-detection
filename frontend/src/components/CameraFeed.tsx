"use client";
import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  MapPin, Crosshair, Maximize2, Camera,
  Upload, Link2, RefreshCw, Play, Pause, Zap,
  Video, VideoOff
} from "lucide-react";
import { InputMode } from "./InputModeSelector";
import { RawDetection } from "@/hooks/useDetections";
import styles from "./CameraFeed.module.css";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Interval between auto-captured frames in Live UAV mode (ms)
const LIVE_CAPTURE_INTERVAL = 4000;

interface Props {
  lat: number;
  lon: number;
  mode: InputMode;
  modelReady: boolean;
  /** Called with raw detection results from the backend inference endpoint */
  onDetections: (raws: RawDetection[]) => void;
  scanInterval?: number;
  /** Called when the live camera active state changes (live mode only) */
  onCameraActive?: (active: boolean) => void;
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
  scanInterval = 1,
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

  // Auto-start scanning when the model finishes loading and a file is already loaded
  useEffect(() => {
    if (modelReady && src) {
      setScanning(true);
    }
    // Only react to modelReady transitions — don't interfere when src or scanning change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelReady]);

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
  lat, lon, modelReady, onDetections, onCameraActive, scanInterval = 1,
}: {
  lat: number; lon: number;
  modelReady: boolean;
  onDetections: (raws: RawDetection[]) => void;
  onCameraActive?: (active: boolean) => void;
  scanInterval?: number;
}) {
  const videoRef      = useRef<HTMLVideoElement>(null);
  const canvasRef     = useRef<HTMLCanvasElement>(null);
  const wrapRef       = useRef<HTMLDivElement>(null);
  const captureRef    = useRef<ReturnType<typeof setInterval> | null>(null);

  // camStatus:
  //   "requesting" — waiting for getUserMedia
  //   "active"     — real webcam stream is live
  //   "unavailable" — permission denied / no hardware
  //   "closed"     — user explicitly toggled camera off
  const [camStatus,   setCamStatus]   = useState<"requesting"|"active"|"unavailable"|"closed">("requesting");
  const [camOn,       setCamOn]       = useState(true);
  const [rtspUrl,     setRtspUrl]     = useState("");
  const [showRtsp,    setShowRtsp]    = useState(false);
  const [autoCapture, setAutoCapture] = useState(false);
  const [lastResult,  setLastResult]  = useState<string | null>(null);

  // The camera is only truly usable when camOn AND we have a real stream
  const cameraIsLive = camStatus === "active";

  // Notify parent whenever camera liveness changes
  useEffect(() => {
    onCameraActive?.(cameraIsLive);
  }, [cameraIsLive, onCameraActive]);

  // Start / stop the real webcam stream
  useEffect(() => {
    if (!camOn) {
      // Stop any existing track and mark closed
      if (videoRef.current?.srcObject) {
        (videoRef.current.srcObject as MediaStream).getTracks().forEach(t => t.stop());
        videoRef.current.srcObject = null;
      }
      setCamStatus("closed");
      setAutoCapture(false);
      setLastResult(null);
      return;
    }

    let stream: MediaStream | null = null;
    setCamStatus("requesting");

    if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ video: true })
        .then(s => {
          stream = s;
          if (videoRef.current) videoRef.current.srcObject = s;
          setCamStatus("active");
        })
        .catch(() => {
          // Permission denied or no camera hardware
          setCamStatus("unavailable");
          setAutoCapture(false);
        });
    } else {
      // Non-secure origin / API not available
      setCamStatus("unavailable");
      setAutoCapture(false);
    }

    return () => {
      stream?.getTracks().forEach(t => t.stop());
    };
  }, [camOn]);

  // Capture a real frame from the webcam and send to backend
  const captureFrame = useCallback(async () => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    // Strict guard: only run inference when camera is genuinely streaming
    if (!camOn || camStatus !== "active" || !canvas || !modelReady || !video) return;

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
  }, [camOn, camStatus, modelReady, onDetections]);

  // Reactive scan manager — only runs when camera is genuinely live
  useEffect(() => {
    if (autoCapture && cameraIsLive && modelReady) {
      captureFrame();
      captureRef.current = setInterval(captureFrame, scanInterval * 1000);
    } else {
      if (captureRef.current) {
        clearInterval(captureRef.current);
        captureRef.current = null;
      }
    }

    return () => {
      if (captureRef.current) {
        clearInterval(captureRef.current);
        captureRef.current = null;
      }
    };
  }, [autoCapture, cameraIsLive, modelReady, scanInterval, captureFrame]);

  // Auto-start scanning once the real camera stream is live and model is ready
  useEffect(() => {
    if (cameraIsLive && modelReady) {
      setAutoCapture(true);
    } else {
      // Stop scanning whenever camera goes offline
      setAutoCapture(false);
    }
  }, [cameraIsLive, modelReady]);

  const toggleAutoCapture = () => setAutoCapture(v => !v);
  const toggleFullscreen  = () => {
    if (!document.fullscreenElement && wrapRef.current) wrapRef.current.requestFullscreen();
    else document.exitFullscreen();
  };

  return (
    <div className={styles.wrap} ref={wrapRef}>
      <canvas ref={canvasRef} hidden />

      {/* Camera source — only the real webcam video element */}
      {cameraIsLive ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          crossOrigin="anonymous"
          className={styles.video}
        />
      ) : (
        <div className={styles.placeholder}>
          <div className={styles.noise} />
          <div className={styles.noSignalText}>
            {camStatus === "requesting" && (
              <><div className={styles.spinner} /><span>ESTABLISHING LINK…</span></>
            )}
            {camStatus === "closed" && (
              <>
                <VideoOff size={40} color="rgba(255,45,149,0.4)" />
                <span style={{ color: "#FF2D95", letterSpacing: "0.15em" }}>CAMERA IS CLOSED</span>
                <span className={styles.noSigSub}>UAV drone survey stream feed is shut down</span>
                <span className={styles.noSigSub} style={{ color: "rgba(255,45,149,0.3)" }}>AI detection is paused — reopen camera to resume</span>
              </>
            )}
            {camStatus === "unavailable" && (
              <>
                <VideoOff size={40} color="rgba(91,33,168,0.5)" />
                <span style={{ color: "#5B21A8", letterSpacing: "0.15em" }}>NO CAMERA DETECTED</span>
                <span className={styles.noSigSub}>No camera hardware or permission was found</span>
                <span className={styles.noSigSub} style={{ color: "rgba(91,33,168,0.4)" }}>Allow camera access in your browser to begin detection</span>
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
          <Link2 size={12} color="#00F0FF" />
          <input
            className={styles.rtspInput}
            placeholder="rtsp://drone-ip:554/stream"
            value={rtspUrl}
            onChange={e => setRtspUrl(e.target.value)}
          />
          <button className={styles.rtspConnect}>CONNECT</button>
        </div>
      )}

      {/* Last detection result badge — only shown when camera is active */}
      {lastResult && cameraIsLive && (
        <div className={styles.liveResultBadge}>
          <Zap size={9} color="#00F0FF" />
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

      {/* Center crosshair — only when live */}
      {cameraIsLive && (
        <div className={styles.crosshair}>
          <Crosshair size={32} color="rgba(0,240,255,0.5)" strokeWidth={0.8} />
        </div>
      )}

      {/* Top HUD */}
      <div className={styles.topHud}>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>REC</span>
          <span className={styles.recDot} style={{ background: cameraIsLive ? "#FF2D95" : "#475569", animationPlayState: cameraIsLive ? "running" : "paused" }} />
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>CAM</span>
          <span
            className={styles.hudValue}
            style={{
              color: cameraIsLive ? "#00F0FF" : camStatus === "unavailable" ? "#5B21A8" : "#FF2D95"
            }}
          >
            {cameraIsLive ? "LIVE" : camStatus === "closed" ? "CLOSED" : camStatus === "unavailable" ? "NO CAMERA" : "CONNECTING"}
          </span>
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>AI</span>
          <span className={styles.hudValue} style={{ color: autoCapture && cameraIsLive ? "#00F0FF" : "rgba(255,255,255,0.45)" }}>
            {autoCapture && cameraIsLive ? "SCANNING" : cameraIsLive ? "IDLE" : "PAUSED"}
          </span>
        </div>
        <div className={styles.spacer} />

        {/* AI scan toggle — only when camera is live */}
        {modelReady && cameraIsLive && (
          <button
            className={`${styles.fsBtn} ${autoCapture ? styles.fsBtnActive : ""}`}
            onClick={toggleAutoCapture}
            title={autoCapture ? "Stop AI frame capture" : "Start AI frame capture"}
          >
            <Zap size={13} color={autoCapture ? "#00F0FF" : "rgba(255,255,255,0.45)"} />
          </button>
        )}

        {/* Manual capture — only when camera is live */}
        {modelReady && cameraIsLive && (
          <button className={styles.fsBtn} onClick={captureFrame} title="Capture & analyse frame now">
            <Camera size={13} color="#00F0FF" />
          </button>
        )}

        <button className={styles.fsBtn} onClick={() => setShowRtsp(v => !v)} title="RTSP URL">
          <Link2 size={13} color="rgba(255,255,255,0.45)" />
        </button>

        {/* Camera Power Toggle */}
        <button
          className={styles.fsBtn}
          onClick={() => setCamOn(v => !v)}
          title={camOn ? "Close Camera Stream" : "Open Camera Stream"}
          style={{
            borderColor: !camOn ? "rgba(255,45,149,0.3)" : undefined,
            background:  !camOn ? "rgba(255,45,149,0.06)" : undefined
          }}
        >
          {camOn && cameraIsLive ? (
            <Video size={13} color="#00F0FF" />
          ) : (
            <VideoOff size={13} color="#FF2D95" />
          )}
        </button>

        <button className={styles.fsBtn} onClick={toggleFullscreen} title="Fullscreen">
          <Maximize2 size={13} color="rgba(255,255,255,0.45)" />
        </button>
      </div>

      {/* Bottom HUD telemetry */}
      <div className={styles.bottomHud}>
        <div className={styles.hudTelRow}>
          <div className={`${styles.telBlock} ${styles.gpsTel}`}>
            <MapPin size={10} color="#00F0FF" />
            <span className={styles.hudLabel}>GPS</span>
            <span className={styles.gpsVal}>{lat.toFixed(4)}°N &nbsp;{lon.toFixed(4)}°E</span>
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
export default function CameraFeed({ lat, lon, mode, modelReady, onDetections, onCameraActive, scanInterval }: Props) {
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
          lat={lat} lon={lon}
          modelReady={modelReady}
          onDetections={onDetections}
          onCameraActive={onCameraActive}
          scanInterval={scanInterval}
        />
      )}

      {/* 2x2 Grid divider overlay */}
      <div className={styles.viewportGridOverlay}>
        <div className={styles.gridLineH} />
        <div className={styles.gridLineV} />
        <span className={`${styles.gridLabel} ${styles.glTl}`}>TL / ZONE A1</span>
        <span className={`${styles.gridLabel} ${styles.glTr}`}>TR / ZONE A2</span>
        <span className={`${styles.gridLabel} ${styles.glBl}`}>BL / ZONE C1</span>
        <span className={`${styles.gridLabel} ${styles.glBr}`}>BR / ZONE C2</span>
      </div>
    </div>
  );
}
