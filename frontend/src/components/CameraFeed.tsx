"use client";
import React, { useEffect, useRef, useState } from "react";
import { MapPin, Crosshair, Maximize2, Camera } from "lucide-react";
import styles from "./CameraFeed.module.css";

interface Props {
  altitude: number;
  speed: number;
  lat: number;
  lon: number;
}

export default function CameraFeed({ altitude, speed, lat, lon }: Props) {
  const videoRef  = useRef<HTMLVideoElement>(null);
  const [camStatus, setCamStatus] = useState<"requesting"|"active"|"unavailable">("requesting");
  const [fullscreen, setFullscreen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Try to attach webcam — simulates drone camera
  useEffect(() => {
    let stream: MediaStream | null = null;
    navigator.mediaDevices?.getUserMedia({ video: true })
      .then(s => {
        stream = s;
        if (videoRef.current) { videoRef.current.srcObject = s; }
        setCamStatus("active");
      })
      .catch(() => setCamStatus("unavailable"));
    return () => { stream?.getTracks().forEach(t => t.stop()); };
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement && wrapRef.current) {
      wrapRef.current.requestFullscreen();
      setFullscreen(true);
    } else {
      document.exitFullscreen();
      setFullscreen(false);
    }
  };

  return (
    <div className={styles.wrap} ref={wrapRef}>
      {/* ─── Camera source ─────────────────────────────── */}
      {camStatus === "active" ? (
        <video ref={videoRef} autoPlay playsInline muted className={styles.video}/>
      ) : (
        <div className={styles.placeholder}>
          <div className={styles.noise}/>
          <div className={styles.noSignalText}>
            {camStatus === "requesting" ? (
              <><div className={styles.spinner}/><span>ESTABLISHING LINK…</span></>
            ) : (
              <>
                <Camera size={40} color="rgba(0,212,255,0.3)"/>
                <span>NO CAMERA SIGNAL</span>
                <span className={styles.noSigSub}>Awaiting drone video feed</span>
              </>
            )}
          </div>
          {/* Animated terrain dots to simulate aerial view */}
          {Array.from({length:24}).map((_,i)=>(
            <div key={i} className={styles.terrainDot} style={{
              left: `${5 + (i%6)*17}%`,
              top:  `${10 + Math.floor(i/6)*22}%`,
              animationDelay: `${i*0.15}s`,
              opacity: 0.3 + Math.random()*0.4,
            }}/>
          ))}
        </div>
      )}

      {/* ─── Scan line ──────────────────────────────────── */}
      <div className={styles.scanLine}/>

      {/* ─── Corner brackets (tactical HUD) ────────────── */}
      <div className={`${styles.corner} ${styles.tl}`}/>
      <div className={`${styles.corner} ${styles.tr}`}/>
      <div className={`${styles.corner} ${styles.bl}`}/>
      <div className={`${styles.corner} ${styles.br}`}/>

      {/* ─── Center crosshair ───────────────────────────── */}
      <div className={styles.crosshair}>
        <Crosshair size={32} color="rgba(0,212,255,0.5)" strokeWidth={0.8}/>
      </div>

      {/* ─── Top HUD bar ────────────────────────────────── */}
      <div className={styles.topHud}>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>REC</span>
          <span className={styles.recDot}/>
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>CAM</span>
          <span className={styles.hudValue} style={{color: camStatus==="active"?"#22c55e":"#ef4444"}}>
            {camStatus==="active"?"LIVE":"OFFLINE"}
          </span>
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>RES</span>
          <span className={styles.hudValue}>1080p</span>
        </div>
        <div className={styles.spacer}/>
        <button className={styles.fsBtn} onClick={toggleFullscreen} title="Fullscreen">
          <Maximize2 size={13} color="#94a3b8"/>
        </button>
      </div>

      {/* ─── Bottom HUD telemetry ───────────────────────── */}
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
            <MapPin size={10} color="#a855f7"/>
            <span className={styles.hudLabel}>GPS</span>
            <span className={styles.gpsVal}>{lat.toFixed(4)}°N  {lon.toFixed(4)}°E</span>
          </div>
          <div className={styles.telBlock}>
            <span className={styles.hudLabel}>HEADING</span>
            <span className={styles.hudBigVal}>247°<span className={styles.hudUnit}>SW</span></span>
          </div>
        </div>
      </div>

      {/* ─── Grid overlay ───────────────────────────────── */}
      <div className={styles.gridOverlay}/>
    </div>
  );
}
