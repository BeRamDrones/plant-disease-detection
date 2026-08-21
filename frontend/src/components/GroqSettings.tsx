"use client";
import React, { useState, useEffect } from "react";
import { Key, Bot, ShieldCheck, CheckCircle2, Cpu, Sparkles, RefreshCw, Lock } from "lucide-react";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

export default function GroqSettings() {
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{
    configured: boolean;
    masked_key?: string;
    vlm_model?: string;
    report_model?: string;
  } | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${BACKEND}/api/inference/groq-status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch {
      /* silent */
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch(`${BACKEND}/api/inference/set-groq-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setMessage("✓ Groq API Key saved successfully! AI Reasoning Engine Activated.");
        setApiKey("");
        fetchStatus();
      } else {
        setMessage(`⚠ Failed to save key: ${data.detail || "Error"}`);
      }
    } catch (err: any) {
      setMessage(`⚠ Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        background: "#0F172A",
        border: "1px solid rgba(56, 189, 248, 0.2)",
        borderRadius: "10px",
        padding: "18px",
        marginTop: "16px",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.4)",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Sparkles size={18} color="#38BDF8" />
          <span style={{ fontFamily: "var(--font-hud)", fontWeight: 800, fontSize: "13px", color: "#F8FAFC", letterSpacing: "0.06em" }}>
            GROQ LLM / VLM REASONING PIPELINE CONFIGURATION
          </span>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            fontSize: "10px",
            fontFamily: "var(--font-hud)",
            padding: "3px 8px",
            borderRadius: "12px",
            background: status?.configured ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)",
            border: status?.configured ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid rgba(245, 158, 11, 0.4)",
            color: status?.configured ? "#10B981" : "#FBBF24",
          }}
        >
          <span
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: status?.configured ? "#10B981" : "#FBBF24",
              boxShadow: status?.configured ? "0 0 6px #10B981" : "none",
            }}
          />
          {status?.configured ? "GROQ LLM ACTIVE" : "KEY NOT CONFIGURED"}
        </span>
      </div>

      <p style={{ fontSize: "11px", color: "#94A3B8", marginBottom: "14px", lineHeight: "1.5" }}>
        Integrating your Groq API Key powers a two-stage hybrid AI pipeline: 
        <strong style={{ color: "#38BDF8" }}> Stage 1 VLM Audit</strong> (Qwen3.6-27B) validates YOLO detections in real-time, and 
        <strong style={{ color: "#34D399" }}> Stage 2 Report Engine</strong> (Llama-3.1-8B) generates structured agronomic field reports upon mission completion.
      </p>

      {/* Models Status Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "16px" }}>
        <div style={{ background: "#151C2A", border: "1px solid #1E293B", borderRadius: "6px", padding: "10px" }}>
          <div style={{ fontSize: "9px", fontFamily: "var(--font-hud)", color: "#64748B", marginBottom: "4px" }}>
            STAGE 1: REAL-TIME VLM AUDITOR
          </div>
          <div style={{ fontSize: "12px", fontFamily: "monospace", fontWeight: 700, color: "#38BDF8" }}>
            {status?.vlm_model || "qwen/qwen3.6-27b"}
          </div>
        </div>
        <div style={{ background: "#151C2A", border: "1px solid #1E293B", borderRadius: "6px", padding: "10px" }}>
          <div style={{ fontSize: "9px", fontFamily: "var(--font-hud)", color: "#64748B", marginBottom: "4px" }}>
            STAGE 2: AGRONOMY REPORT ENGINE
          </div>
          <div style={{ fontSize: "12px", fontFamily: "monospace", fontWeight: 700, color: "#34D399" }}>
            {status?.report_model || "llama-3.1-8b-instant"}
          </div>
        </div>
      </div>

      {/* Key Input Form */}
      <form onSubmit={handleSave} style={{ display: "flex", gap: "8px", flexDirection: "column" }}>
        <label style={{ fontSize: "10px", fontFamily: "var(--font-hud)", color: "#CBD5E1", display: "flex", alignItems: "center", gap: "6px" }}>
          <Key size={12} color="#38BDF8" /> GROQ API KEY (`gsk_...`)
        </label>
        <div style={{ display: "flex", gap: "8px" }}>
          <div style={{ position: "relative", flex: 1, display: "flex", alignItems: "center" }}>
            <input
              type="password"
              placeholder={status?.configured ? `Configured (${status.masked_key})` : "Enter your gsk_... key from console.groq.com"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              style={{
                width: "100%",
                background: "#090D16",
                border: "1px solid #1E293B",
                borderRadius: "6px",
                padding: "8px 12px",
                fontSize: "12px",
                fontFamily: "monospace",
                color: "#F8FAFC",
                outline: "none",
              }}
            />
          </div>
          <button
            type="submit"
            disabled={loading || !apiKey.trim()}
            style={{
              background: apiKey.trim() ? "linear-gradient(135deg, #0284C7, #2563EB)" : "#1E293B",
              color: "#F8FAFC",
              border: "none",
              borderRadius: "6px",
              padding: "0 16px",
              fontSize: "11px",
              fontFamily: "var(--font-hud)",
              fontWeight: 700,
              cursor: apiKey.trim() ? "pointer" : "not-allowed",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              whiteSpace: "nowrap",
            }}
          >
            {loading ? <RefreshCw size={12} className="spin" /> : <ShieldCheck size={12} />}
            {loading ? "SAVING..." : "ACTIVATE GROQ LLM"}
          </button>
        </div>
      </form>

      {message && (
        <div
          style={{
            marginTop: "12px",
            fontSize: "11px",
            fontFamily: "var(--font-hud)",
            color: message.startsWith("✓") ? "#10B981" : "#EF4444",
            background: message.startsWith("✓") ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
            padding: "8px 12px",
            borderRadius: "6px",
            border: message.startsWith("✓") ? "1px solid rgba(16, 185, 129, 0.2)" : "1px solid rgba(239, 68, 68, 0.2)",
          }}
        >
          {message}
        </div>
      )}
    </div>
  );
}
