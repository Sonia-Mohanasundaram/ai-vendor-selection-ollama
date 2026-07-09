import { useState, useCallback, useEffect } from "react";
import { Link } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import * as XLSX from "xlsx";
import Papa from "papaparse";
import {
  Sparkles, Plus, Trash2, History, Upload, FileText, Image as ImageIcon,
  FileSpreadsheet, Trophy, Download, ArrowLeft, Loader2, CheckCircle2,
  TrendingDown, Clock, Wallet, BarChart3, X, Eye,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from "recharts";

import { Button } from "@/components/ui/button";
import { useHistory } from "@/hooks/useHistory";
import type { AnalysisResult, ProcessingStep, FileMeta } from "@/services/types";
import { analyzeFiles, exportToCSV, exportToExcel } from "@/services/analysis";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const STEPS: ProcessingStep[] = [
  { key: "read", label: "Reading files", status: "pending" },
  { key: "extract", label: "Extracting data", status: "pending" },
  { key: "normalize", label: "Normalizing terms", status: "pending" },
  { key: "score", label: "Scoring vendors", status: "pending" },
];

const fileIcon = (name: string) => {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["jpg", "jpeg", "png", "webp"].includes(ext)) return ImageIcon;
  if (["xlsx", "xls", "csv"].includes(ext)) return FileSpreadsheet;
  return FileText;
};

const fmtINR = (n: number) =>
  "₹" + Math.round(n).toLocaleString("en-IN");

const buildOutputFilesMeta = (r: AnalysisResult): FileMeta[] => {
  const csv = exportToCSV(r);
  const csvBytes = new TextEncoder().encode(csv);
  const xlsxBlob = exportToExcel(r);
  return [
    {
      name: `${r.title}.csv`,
      size: csvBytes.byteLength,
      type: "text/csv",
    },
    {
      name: `${r.title}.xlsx`,
      size: xlsxBlob.size,
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
  ];
};

const Dashboard = () => {
  const { items: history, add, remove, clear } = useHistory();
  const [files, setFiles] = useState<File[]>([]);
  const [steps, setSteps] = useState<ProcessingStep[]>(STEPS);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    setFiles((prev) => [...prev, ...accepted].slice(0, 10));
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/*": [".png", ".jpg", ".jpeg", ".webp"],
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
    maxFiles: 10,
  });

  const removeFile = (idx: number) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const startAnalysis = async () => {
    if (files.length < 2) {
      toast.error("Upload at least 2 quotations to compare");
      return;
    }
    setProcessing(true);
    setResult(null);
    setSteps(STEPS.map((s) => ({ ...s, status: "pending" })));

    try {
      const r = await analyzeFiles(files, (key) => {
        setSteps((prev) =>
          prev.map((s) =>
            s.key === key ? { ...s, status: "active" } : s.status === "active" ? { ...s, status: "done" } : s
          )
        );
      });
      const rStored: AnalysisResult = { ...r, output_files: buildOutputFilesMeta(r) };
      setSteps((prev) => prev.map((s) => ({ ...s, status: "done" })));
      setResult(rStored);
      add(rStored);
      setSelectedHistoryId(rStored.id);
      toast.success(`Analysis complete — ${rStored.best.vendor_name} recommended`);
    } catch (e: any) {
      toast.error(e?.message ?? "Analysis failed");
    } finally {
      setProcessing(false);
    }
  };

  const newAnalysis = () => {
    setFiles([]);
    setResult(null);
    setSelectedHistoryId(null);
    setSteps(STEPS);
  };

  const loadFromHistory = (r: AnalysisResult) => {
    setResult(r);
    setSelectedHistoryId(r.id);
    setFiles([]);
  };

  const downloadCSV = () => {
    if (!result) return;
    const blob = new Blob([exportToCSV(result)], { type: "text/csv" });
    triggerDownload(blob, `${result.title}.csv`);
  };

  const downloadXLSX = () => {
    if (!result) return;
    triggerDownload(exportToExcel(result), `${result.title}.xlsx`);
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* Sidebar */}
      <aside className="hidden md:flex w-72 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground">
        <div className="p-4 border-b border-sidebar-border">
          <Link to="/" className="flex items-center gap-2 mb-4">
            <div className="h-8 w-8 rounded-lg gradient-primary flex items-center justify-center shadow-glow">
              <Sparkles className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="font-bold">QuoteIQ</span>
          </Link>
          <Button onClick={newAnalysis} className="w-full gradient-primary text-primary-foreground border-0 hover:opacity-90">
            <Plus className="h-4 w-4 mr-2" /> New Analysis
          </Button>
        </div>
        <div className="flex items-center justify-between px-4 py-3 text-xs uppercase tracking-wider text-muted-foreground">
          <span className="flex items-center gap-1.5"><History className="h-3.5 w-3.5" /> History</span>
          {history.length > 0 && (
            <button onClick={clear} className="hover:text-destructive transition" title="Clear all">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
          {history.length === 0 && (
            <div className="px-3 py-8 text-center text-xs text-muted-foreground">
              Your past analyses will appear here.
            </div>
          )}
          {history.map((h) => (
            <button
              key={h.id}
              onClick={() => loadFromHistory(h)}
              className={cn(
                "group w-full text-left px-3 py-2.5 rounded-lg text-sm transition flex items-start justify-between gap-2",
                selectedHistoryId === h.id
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "hover:bg-sidebar-accent/60"
              )}
            >
              <div className="min-w-0 flex-1">
                <div className="font-medium truncate">{h.best.vendor_name}</div>
                <div className="text-xs text-muted-foreground truncate">
                  {h.vendors.length} vendors · {new Date(h.createdAt).toLocaleDateString()}
                </div>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); remove(h.id); if (selectedHistoryId === h.id) newAnalysis(); }}
                className="opacity-0 group-hover:opacity-100 transition text-muted-foreground hover:text-destructive shrink-0 mt-0.5"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </button>
          ))}
        </div>
        <div className="p-3 border-t border-sidebar-border">
          <Link to="/" className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to landing
          </Link>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-x-hidden">
        <div className="border-b">
          <div className="px-6 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">Vendor Comparison Dashboard</h1>
              <p className="text-xs text-muted-foreground">Drop quotations and let the engine do the work.</p>
            </div>
            {result && (
              <div className="flex gap-2">
                {files.length > 0 && (
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="outline" size="sm">
                        <Eye className="h-4 w-4 mr-1.5" /> Preview Files
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                      <DialogHeader>
                        <DialogTitle>Uploaded Files Preview</DialogTitle>
                      </DialogHeader>
                      <div className="grid gap-4 mt-4">
                        {files.map((file, i) => (
                          <div key={i} className="border rounded-lg p-4">
                            <h3 className="font-medium mb-2">{file.name}</h3>
                            {file.type.startsWith("image/") ? (
                              <img src={URL.createObjectURL(file)} alt={file.name} className="max-w-full h-auto max-h-[400px] object-contain mx-auto" />
                            ) : file.type === "application/pdf" ? (
                              <iframe src={URL.createObjectURL(file)} className="w-full h-[500px]" title={file.name} />
                            ) : (
                              <div className="text-sm text-muted-foreground p-4 bg-muted/30 rounded text-center">Preview not available for this file type.</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </DialogContent>
                  </Dialog>
                )}
                <Button variant="outline" size="sm" onClick={downloadCSV}>
                  <Download className="h-4 w-4 mr-1.5" /> CSV
                </Button>
                <Button variant="outline" size="sm" onClick={downloadXLSX}>
                  <Download className="h-4 w-4 mr-1.5" /> Excel
                </Button>
              </div>
            )}
          </div>
        </div>

        <div className="p-6 space-y-6">
          {!result && (
            <>
              {/* Upload */}
              <div
                {...getRootProps()}
                className={cn(
                  "rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition",
                  isDragActive ? "border-primary bg-accent" : "border-border hover:border-primary/50 hover:bg-accent/30"
                )}
              >
                <input {...getInputProps()} />
                <div className="h-14 w-14 rounded-2xl gradient-primary mx-auto flex items-center justify-center shadow-glow mb-4">
                  <Upload className="h-7 w-7 text-primary-foreground" />
                </div>
                <div className="font-semibold text-lg">
                  {isDragActive ? "Drop them here" : "Drop vendor quotations"}
                </div>
                <div className="text-sm text-muted-foreground mt-1">
                  PDF, images, CSV or Excel · 2–10 files
                </div>
              </div>

              {files.length > 0 && (
                <div className="rounded-2xl border bg-card shadow-card">
                  <div className="px-5 py-3 border-b text-sm font-medium flex items-center justify-between">
                    <span>{files.length} file{files.length > 1 ? "s" : ""} ready</span>
                    <Button size="sm" onClick={startAnalysis} disabled={processing} className="gradient-primary text-primary-foreground border-0 hover:opacity-90">
                      {processing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
                      Run Analysis
                    </Button>
                  </div>
                  <div className="p-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {files.map((f, i) => {
                      const Icon = fileIcon(f.name);
                      return (
                        <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-muted/40 group">
                          <div className="h-10 w-10 rounded-lg bg-card flex items-center justify-center">
                            <Icon className="h-5 w-5 text-primary" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium truncate">{f.name}</div>
                            <div className="text-xs text-muted-foreground">{(f.size / 1024).toFixed(1)} KB</div>
                          </div>
                          <button onClick={() => removeFile(i)} className="opacity-0 group-hover:opacity-100 transition text-muted-foreground hover:text-destructive">
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {processing && (
                <div className="rounded-2xl border bg-card shadow-card p-6">
                  <div className="text-sm font-medium mb-4">Processing</div>
                  <div className="space-y-3">
                    {steps.map((s) => (
                      <div key={s.key} className="flex items-center gap-3">
                        <div className={cn(
                          "h-7 w-7 rounded-full flex items-center justify-center shrink-0",
                          s.status === "done" && "bg-success text-success-foreground",
                          s.status === "active" && "gradient-primary text-primary-foreground",
                          s.status === "pending" && "bg-muted text-muted-foreground"
                        )}>
                          {s.status === "done" ? <CheckCircle2 className="h-4 w-4" /> :
                           s.status === "active" ? <Loader2 className="h-4 w-4 animate-spin" /> :
                           <span className="text-xs">·</span>}
                        </div>
                        <span className={cn("text-sm", s.status === "pending" && "text-muted-foreground")}>{s.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {!processing && files.length === 0 && (
                <div className="text-center text-sm text-muted-foreground py-12">
                  Tip: Try mixing CSV and Excel quotations to see normalization in action.
                </div>
              )}
            </>
          )}

          {result && <ResultView result={result} />}
        </div>
      </main>
    </div>
  );
};

const ResultView = ({ result }: { result: AnalysisResult }) => {
  const minCost = Math.min(...result.vendors.map((v) => v.total_cost));
  const minDelivery = Math.min(...result.vendors.map((v) => v.delivery_days));
  const maxScore = Math.max(...result.vendors.map((v) => v.final_score));

  const chartData = result.vendors.map((v) => ({
    name: v.vendor_name.length > 14 ? v.vendor_name.slice(0, 14) + "…" : v.vendor_name,
    base: Math.round(v.base_amount),
    gst: Math.round(v.gst_amount),
    freight: Math.round(v.freight),
    credit: Math.round(v.credit_cost),
    delay: Math.round(v.delay_penalty_cost),
    risk: Math.round(v.missing_data_risk_cost),
  }));

  const chartColors = [
    "hsl(var(--primary))",
    "hsl(var(--secondary))",
    "hsl(var(--info))",
    "hsl(var(--gold))",
    "hsl(var(--accent-foreground))",
    "hsl(var(--destructive))",
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Winner */}
      <div className="rounded-2xl gradient-primary text-primary-foreground p-6 md:p-8 shadow-elevated relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,white_0%,transparent_60%)] opacity-15" />
        <div className="relative grid md:grid-cols-[1fr_auto] gap-6 items-center">
          <div>
            <div className="flex items-center gap-2 text-sm uppercase tracking-wider opacity-90">
              <Trophy className="h-4 w-4" /> Recommended Vendor
            </div>
            <div className="text-3xl md:text-4xl font-bold mt-2">{result.best.vendor_name}</div>
            <div className="text-sm opacity-90 mt-1">
              Rank #1 · Final score {(result.best.final_score * 100).toFixed(1)}% · Total {fmtINR(result.best.total_cost)}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { l: "Score", v: `${(result.best.final_score * 100).toFixed(0)}%`, i: BarChart3 },
              { l: "Delivery", v: `${result.best.delivery_days}d`, i: Clock },
              { l: "Terms", v: `Net ${result.best.payment_days}`, i: Wallet },
            ].map((m) => (
              <div key={m.l} className="bg-white/15 rounded-xl px-4 py-3 text-center min-w-[80px]">
                <m.i className="h-4 w-4 mx-auto mb-1 opacity-90" />
                <div className="text-lg font-bold">{m.v}</div>
                <div className="text-[10px] uppercase opacity-80">{m.l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Comparison */}
      <div className="rounded-2xl border bg-card shadow-card overflow-hidden">
        <div className="px-5 py-3 border-b font-medium text-sm flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-primary" /> Vendor Comparison
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-muted-foreground text-xs uppercase tracking-wider">
              <tr>
                {["Rank","Vendor","Item","Total","Delivery","Payment","Score"].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.vendors.map((v) => (
                <tr key={v.id} className="border-t hover:bg-muted/30">
                  <td className="px-4 py-3 font-semibold">#{v.rank}</td>
                  <td className="px-4 py-3 font-medium">
                    {v.vendor_name}
                    {v.id === result.best.id && (
                      <span className="ml-2 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full gradient-gold text-gold-foreground font-bold">Winner</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{v.item_name}</td>
                  <td className={cn("px-4 py-3 font-medium", v.total_cost === minCost && "text-success")}>
                    {fmtINR(v.total_cost)}
                  </td>
                  <td className={cn("px-4 py-3", v.delivery_days === minDelivery && "text-info font-medium")}>
                    {v.delivery_days}d
                  </td>
                  <td className="px-4 py-3">Net {v.payment_days}</td>
                  <td className={cn("px-4 py-3 font-semibold", v.final_score === maxScore && "text-gold-foreground")}>
                    {(v.final_score * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Explanation + Differences */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="rounded-2xl border bg-card shadow-card p-6">
          <div className="flex items-center gap-2 font-medium mb-4">
            <Sparkles className="h-4 w-4 text-primary" /> Why this vendor wins
          </div>
          <ul className="space-y-3">
            {result.explanation.map((p, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />
                <span>{p}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border bg-card shadow-card overflow-hidden">
          <div className="px-5 py-3 border-b font-medium text-sm flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-primary" /> Gaps vs. best in class
          </div>
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-muted-foreground text-xs uppercase tracking-wider">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium">Vendor</th>
                <th className="px-4 py-2.5 text-right font-medium">Cost gap</th>
                <th className="px-4 py-2.5 text-right font-medium">Delivery gap</th>
                <th className="px-4 py-2.5 text-right font-medium">Terms gap</th>
              </tr>
            </thead>
            <tbody>
              {result.differences.map((d) => (
                <tr key={d.vendor_name} className="border-t">
                  <td className="px-4 py-2.5 font-medium">{d.vendor_name}</td>
                  <td className={cn("px-4 py-2.5 text-right", d.cost_diff === 0 && "text-success font-medium")}>
                    {`+${fmtINR(d.cost_diff)}`}
                  </td>
                  <td className={cn("px-4 py-2.5 text-right", d.delivery_diff === 0 && "text-info font-medium")}>
                    {d.delivery_diff === 0 ? "0d" : `+${d.delivery_diff}d`}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {d.terms_diff === 0 ? "0d" : `-${d.terms_diff}d`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Cost Breakdown chart */}
      <div className="rounded-2xl border bg-card shadow-card p-6">
        <div className="flex items-center gap-2 font-medium mb-4">
          <Wallet className="h-4 w-4 text-primary" /> Cost Breakdown
        </div>
        <div className="h-72">
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={12} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "0.75rem" }}
                formatter={(v: number) => fmtINR(v)}
              />
              <Bar dataKey="base" stackId="a" name="Base" fill={chartColors[0]} />
              <Bar dataKey="gst" stackId="a" name="GST" fill={chartColors[1]} />
              <Bar dataKey="freight" stackId="a" name="Freight" fill={chartColors[2]} />
              <Bar dataKey="credit" stackId="a" name="Credit cost" fill={chartColors[3]} />
              <Bar dataKey="delay" stackId="a" name="Delay penalty" fill={chartColors[4]} />
              <Bar dataKey="risk" stackId="a" name="Missing data risk" fill={chartColors[5]} radius={[8, 8, 0, 0]}>
                {chartData.map((_, i) => <Cell key={i} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Ranking summary */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { l: "Vendors compared", v: result.vendors.length, i: BarChart3 },
          { l: "Lowest total cost", v: fmtINR(minCost), i: Wallet, accent: "text-success" },
          { l: "Fastest delivery", v: `${minDelivery} days`, i: Clock, accent: "text-info" },
          { l: "Top score", v: `${(maxScore * 100).toFixed(1)}%`, i: Trophy, accent: "text-gold-foreground" },
        ].map((m) => (
          <div key={m.l} className="rounded-2xl border bg-card shadow-card p-5">
            <m.i className="h-5 w-5 text-muted-foreground mb-2" />
            <div className="text-xs uppercase tracking-wider text-muted-foreground">{m.l}</div>
            <div className={cn("text-2xl font-bold mt-1", m.accent)}>{m.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

function triggerDownload(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default Dashboard;
