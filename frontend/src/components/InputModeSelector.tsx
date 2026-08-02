"use client";
import React from "react";
import { Camera, Film, Radio } from "lucide-react";
import styles from "./InputModeSelector.module.css";

export type InputMode = "image" | "video" | "live";

interface Tab {
  id: InputMode;
  label: string;
  icon: React.ReactNode;
  hint: string;
}

const TABS: Tab[] = [
  {
    id: "image",
    label: "IMAGE",
    icon: <Camera size={13} strokeWidth={1.8} />,
    hint: "Upload an image for analysis",
  },
  {
    id: "video",
    label: "VIDEO",
    icon: <Film size={13} strokeWidth={1.8} />,
    hint: "Upload a video for frame-by-frame scan",
  },
  {
    id: "live",
    label: "LIVE UAV",
    icon: <Radio size={13} strokeWidth={1.8} />,
    hint: "Connect to live drone stream",
  },
];

interface Props {
  mode: InputMode;
  onModeChange: (m: InputMode) => void;
  modelReady: boolean;
}

export default function InputModeSelector({ mode, onModeChange, modelReady }: Props) {
  return (
    <div className={styles.wrap}>
      {TABS.map((tab) => {
        const active = tab.id === mode;
        return (
          <button
            key={tab.id}
            className={`${styles.tab} ${active ? styles.active : ""} ${!modelReady ? styles.disabled : ""}`}
            onClick={() => modelReady && onModeChange(tab.id)}
            title={modelReady ? tab.hint : "Waiting for model to load…"}
            disabled={!modelReady}
          >
            <span className={styles.tabIcon}>{tab.icon}</span>
            <span className={styles.tabLabel}>{tab.label}</span>
            {active && <span className={styles.activeDot} />}
          </button>
        );
      })}
      {!modelReady && (
        <span className={styles.lockBadge}>MODEL LOADING…</span>
      )}
    </div>
  );
}
