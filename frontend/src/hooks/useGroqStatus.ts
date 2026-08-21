"use client";
import { useState, useEffect } from "react";

export interface GroqStatus {
  configured: boolean;
  masked_key?: string;
  vlm_model?: string;
  report_model?: string;
  loading: boolean;
}

const BACKEND = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

export function useGroqStatus(): GroqStatus & { refresh: () => void } {
  const [status, setStatus] = useState<GroqStatus>({
    configured: false,
    vlm_model: "qwen/qwen3.6-27b",
    report_model: "llama-3.1-8b-instant",
    loading: true,
  });

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${BACKEND}/api/inference/groq-status`, {
        cache: "no-store",
      });
      if (res.ok) {
        const data = await res.json();
        setStatus({
          configured: !!data.configured,
          masked_key: data.masked_key,
          vlm_model: data.vlm_model || "qwen/qwen3.6-27b",
          report_model: data.report_model || "llama-3.1-8b-instant",
          loading: false,
        });
      } else {
        setStatus(prev => ({ ...prev, loading: false }));
      }
    } catch {
      setStatus(prev => ({ ...prev, loading: false }));
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return { ...status, refresh: fetchStatus };
}
