"use client";
import React, { useEffect, useState } from "react";
import { Cpu, Wifi, WifiOff } from "lucide-react";
import { ModelStatus } from "@/hooks/useModelStatus";
import styles from "./ModelGate.module.css";

interface Props {
  status: ModelStatus;
}

export default function ModelGate({ status }: Props) {
  const [visible, setVisible] = useState(true);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    if (status.ready && !status.loading) {
      // Trigger fade-out then unmount
      setFading(true);
      const t = setTimeout(() => setVisible(false), 700);
      return () => clearTimeout(t);
    }
  }, [status.ready, status.loading]);

  if (!visible) return null;

  return (
    <div className={`${styles.overlay} ${fading ? styles.fadeOut : ""}`}>
      {/* Animated background grid */}
      <div className={styles.gridBg} />

      {/* Corner brackets */}
      <div className={`${styles.corner} ${styles.tl}`} />
      <div className={`${styles.corner} ${styles.tr}`} />
      <div className={`${styles.corner} ${styles.bl}`} />
      <div className={`${styles.corner} ${styles.br}`} />

      {/* Center card */}
      <div className={styles.card}>
        {/* Logo / icon */}
        <div className={styles.iconWrap}>
          <div className={styles.ring1} />
          <div className={styles.ring2} />
          <Cpu size={36} color="#00F0FF" strokeWidth={1.2} />
        </div>

        {/* Branding */}
        <div className={styles.brand}>PROJECT JATAYU</div>
        <div className={styles.sub}>MISSION CONTROL SYSTEM v2</div>

        {/* Status block */}
        <div className={styles.statusBlock}>
          {status.error ? (
            <>
              <WifiOff size={16} color="#EF4444" />
              <span className={styles.statusText} style={{ color: "#EF4444" }}>
                BACKEND UNREACHABLE — RETRYING…
              </span>
            </>
          ) : (
            <>
              <div className={styles.spinnerWrap}>
                <div className={styles.spinner} />
              </div>
              <span className={styles.statusText}>
                LOADING PARENT MODEL
                <span className={styles.modelName}> {status.model_name.toUpperCase()}</span>
              </span>
            </>
          )}
        </div>

        {/* Progress bar */}
        <div className={styles.progressBar}>
          <div
            className={styles.progressFill}
            style={{ animationPlayState: status.error ? "paused" : "running" }}
          />
        </div>

        {/* Info pills */}
        <div className={styles.pills}>
          <span className={styles.pill}>
            <Wifi size={9} />
            {status.torch_available ? "TORCH ENABLED" : "MOCK MODE"}
          </span>
          <span className={styles.pill}>
            <Cpu size={9} />
            PARENT MODEL: {status.model_name.toUpperCase()}
          </span>
        </div>

        <div className={styles.hint}>
          Detection will start automatically once the model is ready
        </div>
      </div>
    </div>
  );
}
