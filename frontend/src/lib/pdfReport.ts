import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { Detection, MissionData, MissionSummary, diseaseColor } from "@/lib/types";

function hexToRgb(hex: string): [number,number,number] {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return [r,g,b];
}

export function generateMissionPDF(
  summary: MissionSummary,
  detections: Detection[],
  elapsedSeconds: number
): void {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const W = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();

  // ── Header bar ──────────────────────────────────────────────
  doc.setFillColor(5, 8, 16);
  doc.rect(0, 0, W, pageH, "F");

  doc.setFillColor(0, 20, 40);
  doc.rect(0, 0, W, 42, "F");

  doc.setDrawColor(0, 212, 255);
  doc.setLineWidth(0.4);
  doc.line(0, 42, W, 42);

  // Title
  doc.setFont("helvetica","bold");
  doc.setFontSize(20);
  doc.setTextColor(0, 212, 255);
  doc.text("PROJECT JATAYU", 14, 16);
  doc.setFontSize(10);
  doc.setTextColor(148,163,184);
  doc.text("DRONE PLANT DISEASE DETECTION — MISSION REPORT", 14, 23);

  // Mission badge top-right
  const now = new Date().toLocaleString();
  doc.setFontSize(8);
  doc.setTextColor(100,116,139);
  doc.text(`Generated: ${now}`, W - 14, 16, { align: "right" });
  doc.setTextColor(0,212,255);
  doc.setFontSize(9);
  doc.text(`Mission #${summary.mission.mission_id}`, W - 14, 23, { align: "right" });

  // Health score gauge area
  const hs = summary.health_score;
  const col = hs >= 70 ? [34,197,94] : hs >= 40 ? [245,158,11] : [239,68,68];
  doc.setFillColor(col[0],col[1],col[2]);
  doc.roundedRect(14, 28, 60, 10, 2, 2, "F");
  doc.setFont("helvetica","bold");
  doc.setFontSize(9);
  doc.setTextColor(5,8,16);
  doc.text(`HEALTH SCORE  ${hs.toFixed(1)}%`, 44, 34.5, { align:"center" });

  // ── Mission Info table ─────────────────────────────────────
  let y = 50;
  doc.setFont("helvetica","bold");
  doc.setFontSize(10);
  doc.setTextColor(0,212,255);
  doc.text("MISSION METADATA", 14, y); y += 4;
  doc.setDrawColor(0,212,255); doc.setLineWidth(0.2);
  doc.line(14, y, W-14, y); y += 3;

  const h = Math.floor(elapsedSeconds/3600).toString().padStart(2,"0");
  const m = Math.floor((elapsedSeconds%3600)/60).toString().padStart(2,"0");
  const s = (elapsedSeconds%60).toString().padStart(2,"0");

  const meta = [
    ["Drone ID",    summary.mission.drone_id,         "Phase",      summary.mission.phase.toUpperCase()],
    ["Status",      summary.mission.status.toUpperCase(),"Crop Class", summary.mission.crop_class ?? "N/A"],
    ["Mission Start", new Date(summary.mission.created_at).toLocaleString(), "Flight Duration", `${h}:${m}:${s}`],
    ["Total Detections", detections.length.toString(),   "Zones Scanned", summary.zones_breakdown.filter(z=>z.detection_count>0).length.toString()],
  ];

  autoTable(doc, {
    startY: y,
    body: meta.map(row => [
      { content: row[0], styles: { textColor:[148,163,184], fontStyle:"bold" } },
      { content: row[1], styles: { textColor:[226,232,240] } },
      { content: row[2], styles: { textColor:[148,163,184], fontStyle:"bold" } },
      { content: row[3], styles: { textColor:[226,232,240] } },
    ]),
    theme: "plain",
    styles: { fontSize: 9, cellPadding: 2.5, fillColor:[10,14,26] },
    columnStyles: { 0:{cellWidth:35}, 1:{cellWidth:60}, 2:{cellWidth:35}, 3:{cellWidth:46} },
    margin: { left:14, right:14 },
  });

  // ── Zone Breakdown ─────────────────────────────────────────
  y = (doc as any).lastAutoTable.finalY + 8;
  doc.setFont("helvetica","bold"); doc.setFontSize(10);
  doc.setTextColor(0,212,255);
  doc.text("ZONE ANALYSIS BREAKDOWN", 14, y); y += 4;
  doc.setDrawColor(0,212,255); doc.line(14, y, W-14, y); y += 3;

  autoTable(doc, {
    startY: y,
    head: [["Zone","Detections","Dominant Disease","Avg Confidence","Status"]],
    body: summary.zones_breakdown.map(z => {
      const dc = z.dominant_class ?? "—";
      const status = !z.dominant_class||z.dominant_class==="healthy" ? "✓ HEALTHY" : "⚠ DISEASED";
      return [
        z.zone_label,
        z.detection_count.toString(),
        dc.replace(/_/g," ").toUpperCase(),
        z.avg_confidence > 0 ? `${(z.avg_confidence*100).toFixed(1)}%` : "—",
        status,
      ];
    }),
    theme: "plain",
    headStyles: { fillColor:[0,30,50], textColor:[0,212,255], fontStyle:"bold", fontSize:8 },
    bodyStyles: { fillColor:[10,14,26], textColor:[226,232,240], fontSize:8, cellPadding:2.5 },
    alternateRowStyles: { fillColor:[15,22,37] },
    columnStyles: { 4: { halign:"center" } },
    margin: { left:14, right:14 },
    didDrawCell: (data: any) => {
      if (data.section === "body" && data.column.index === 4) {
        const txt = data.cell.raw as string;
        if (txt.includes("HEALTHY")) doc.setTextColor(34,197,94);
        else doc.setTextColor(239,68,68);
      }
    },
  });

  // ── Detection Log (last 50) ───────────────────────────────
  const recentDets = detections.slice(0, 50);
  if (recentDets.length > 0) {
    if ((doc as any).lastAutoTable.finalY + 30 > pageH - 20) doc.addPage();
    y = (doc as any).lastAutoTable.finalY + 10;

    // dark bg on new page
    const curPage = doc.getCurrentPageInfo().pageNumber;
    doc.setFillColor(5,8,16);
    doc.rect(0,0,W,pageH,"F");

    doc.setFont("helvetica","bold"); doc.setFontSize(10);
    doc.setTextColor(0,212,255);
    doc.text(`DETECTION LOG (last ${recentDets.length})`, 14, y); y += 4;
    doc.setDrawColor(0,212,255); doc.line(14, y, W-14, y); y += 3;

    autoTable(doc, {
      startY: y,
      head: [["#","Class","Confidence","Zone","GPS Coords","Timestamp"]],
      body: recentDets.map((d,i) => [
        (i+1).toString(),
        d.detected_class.replace(/_/g," ").toUpperCase(),
        `${(d.confidence_score*100).toFixed(1)}%`,
        d.zone_label ?? "—",
        `${d.lat.toFixed(5)}, ${d.lon.toFixed(5)}`,
        new Date(d.detected_at).toLocaleTimeString(),
      ]),
      theme: "plain",
      headStyles: { fillColor:[0,30,50], textColor:[0,212,255], fontStyle:"bold", fontSize:7.5 },
      bodyStyles: { fillColor:[10,14,26], textColor:[226,232,240], fontSize:7.5, cellPadding:2 },
      alternateRowStyles: { fillColor:[15,22,37] },
      margin: { left:14, right:14 },
    });
  }

  // ── Footer on each page ───────────────────────────────────
  const totalPages = doc.getNumberOfPages();
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p);
    doc.setDrawColor(0,212,255); doc.setLineWidth(0.2);
    doc.line(14, pageH-10, W-14, pageH-10);
    doc.setFont("helvetica","normal"); doc.setFontSize(7);
    doc.setTextColor(71,85,105);
    doc.text("Project Jatayu — Confidential Mission Report", 14, pageH-5);
    doc.text(`Page ${p} of ${totalPages}`, W-14, pageH-5, { align:"right" });
  }

  const filename = `jatayu_mission_${summary.mission.mission_id}_report.pdf`;
  doc.save(filename);
}
