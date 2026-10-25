import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import {
  ArrowLeft, CheckCircle2, Download, Eye, FileSpreadsheet, FileText,
  History, Image as ImageIcon, Loader2, Plus, Sparkles, Trash2, Trophy,
  Upload, X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useHistory } from "@/hooks/useHistory";
import type { AnalysisResult, ProcessingStep, FileMeta, EvaluatedVendor } from "@/services/types";
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
  { key: "read", label: "Preparing quotations", status: "pending" },
  { key: "extract", label: "Extracting and normalizing evidence", status: "pending" },
  { key: "evaluate", label: "Evaluating with Ollama", status: "pending" },
  { key: "complete", label: "Validating recommendations", status: "pending" },
];

const fileIcon = (name: string) => {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["jpg", "jpeg", "png", "webp"].includes(ext)) return ImageIcon;
  if (["xlsx", "xls", "csv"].includes(ext)) return FileSpreadsheet;
  return FileText;
};

const fmtINR = (n: number | null) =>
  n == null ? "Not available" : `₹${Math.round(n).toLocaleString("en-IN")}`;

const fmtQuotationAmount = (
  vendor: EvaluatedVendor,
  field: string,
  amount: number | null
) =>
  vendor.field_status?.[field] === "not_applicable"
    ? "Not applicable"
    : fmtINR(amount);

const buildOutputFilesMeta = (result: AnalysisResult): FileMeta[] => {
  const csv = exportToCSV(result);
  const xlsx = exportToExcel(result);
  return [
    { name: `${result.title}.csv`, size: new TextEncoder().encode(csv).byteLength, type: "text/csv" },
    {
      name: `${result.title}.xlsx`,
      size: xlsx.size,
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
  ];
};

const Dashboard = () => {
  const { items: history, add, remove, clear } = useHistory();
  const [files, setFiles] = useState<File[]>([]);
  const [requirements, setRequirements] = useState("");
  const [steps, setSteps] = useState<ProcessingStep[]>(STEPS);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    setFiles((previous) => [...previous, ...accepted].slice(0, 10));
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "image/*": [".png", ".jpg", ".jpeg", ".webp"],
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
    maxFiles: 10,
  });

  const startAnalysis = async () => {
    if (files.length < 2) {
      toast.error("Upload at least 2 quotations to compare");
      return;
    }
    setProcessing(true);
    setResult(null);
    setSteps(STEPS.map((step) => ({ ...step, status: "pending" })));
    try {
      const evaluated = await analyzeFiles(files, requirements, (activeKey) => {
        setSteps((previous) =>
          previous.map((step) => ({
            ...step,
            status:
              step.key === activeKey
                ? "active"
                : step.status === "active" ||
                    STEPS.findIndex((candidate) => candidate.key === step.key) <
                      STEPS.findIndex((candidate) => candidate.key === activeKey)
                  ? "done"
                  : "pending",
          }))
        );
      });
      const stored = { ...evaluated, output_files: buildOutputFilesMeta(evaluated) };
      setSteps((previous) => previous.map((step) => ({ ...step, status: "done" })));
      setResult(stored);
      add(stored);
      setSelectedHistoryId(stored.id);
      toast.success(stored.inconclusive ? "Evaluation complete — no verified winner" : "AI evaluation complete");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "AI evaluation failed");
    } finally {
      setProcessing(false);
    }
  };

  const newAnalysis = () => {
    setFiles([]);
    setRequirements("");
    setResult(null);
    setSelectedHistoryId(null);
    setSteps(STEPS);
  };

  const loadFromHistory = (analysis: AnalysisResult) => {
    if (!analysis.evaluation_summary) {
      toast.error("This is a legacy rule-based analysis. Run a new analysis to get an Ollama evaluation.");
      return;
    }
    setResult(analysis);
    setSelectedHistoryId(analysis.id);
    setFiles([]);
  };

  const download = (kind: "csv" | "xlsx") => {
    if (!result) return;
    const blob =
      kind === "csv"
        ? new Blob([exportToCSV(result)], { type: "text/csv" })
        : exportToExcel(result);
    triggerDownload(blob, `${result.title}.${kind}`);
  };

  return (
    <div className="min-h-screen flex bg-background">
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
          {history.length === 0 ? (
            <div className="px-3 py-8 text-center text-xs text-muted-foreground">
              Your past analyses will appear here.
            </div>
          ) : history.map((entry) => (
            <div
              key={entry.id}
              className={cn(
                "group w-full px-3 py-2.5 rounded-lg text-sm transition flex items-start justify-between gap-2",
                selectedHistoryId === entry.id ? "bg-sidebar-accent text-sidebar-accent-foreground" : "hover:bg-sidebar-accent/60"
              )}
            >
              <button onClick={() => loadFromHistory(entry)} className="min-w-0 flex-1 text-left">
                <div className="font-medium truncate">
                  {entry.best?.vendor_name ?? (entry.best ? "Selected vendor (name unknown)" : "Inconclusive evaluation")}
                </div>
                <div className="text-xs text-muted-foreground truncate">
                  {entry.vendors?.length ?? 0} vendors · {new Date(entry.createdAt).toLocaleDateString()}
                </div>
              </button>
              <button
                onClick={() => {
                  remove(entry.id);
                  if (selectedHistoryId === entry.id) newAnalysis();
                }}
                className="opacity-0 group-hover:opacity-100 transition text-muted-foreground hover:text-destructive shrink-0 mt-0.5"
                aria-label="Remove analysis from history"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
        <div className="p-3 border-t border-sidebar-border">
          <Link to="/" className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to landing
          </Link>
        </div>
      </aside>

      <main className="flex-1 overflow-x-hidden">
        <div className="border-b">
          <div className="px-6 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">Vendor Comparison Dashboard</h1>
              <p className="text-xs text-muted-foreground">Compare quotations against your requirements with a local AI model.</p>
            </div>
            {result && (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => download("csv")}><Download className="h-4 w-4 mr-1.5" /> CSV</Button>
                <Button variant="outline" size="sm" onClick={() => download("xlsx")}><Download className="h-4 w-4 mr-1.5" /> Excel</Button>
              </div>
            )}
          </div>
        </div>

        <div className="p-6 space-y-6">
          {!result ? (
            <>
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
                <div className="font-semibold text-lg">{isDragActive ? "Drop them here" : "Drop vendor quotations"}</div>
                <div className="text-sm text-muted-foreground mt-1">PDF, DOCX, images, CSV or Excel · 2–10 files</div>
              </div>

              <div className="rounded-2xl border bg-card shadow-card p-5 space-y-2">
                <label htmlFor="requirements" className="text-sm font-medium">Purchase priorities and mandatory constraints</label>
                <Textarea
                  id="requirements"
                  value={requirements}
                  onChange={(event) => setRequirements(event.target.value)}
                  maxLength={2000}
                  placeholder="For example: prioritize delivery within 10 days; budget must not exceed ₹2,00,000; identify missing tax or freight details."
                  rows={3}
                />
                <p className="text-xs text-muted-foreground">
                  State what matters most. Explicit maximum budgets and delivery limits are checked against extracted values.
                  For hard checks, use wording such as “maximum budget INR 100000” and “delivery within 14 days.”
                </p>
              </div>

              {files.length > 0 && (
                <div className="rounded-2xl border bg-card shadow-card">
                  <div className="px-5 py-3 border-b text-sm font-medium flex items-center justify-between">
                    <span>{files.length} file{files.length > 1 ? "s" : ""} ready</span>
                    <div className="flex gap-2">
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button variant="outline" size="sm"><Eye className="h-4 w-4 mr-1.5" /> Preview</Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                          <DialogHeader><DialogTitle>Uploaded Files Preview</DialogTitle></DialogHeader>
                          <div className="grid gap-4 mt-4">
                            {files.map((file) => (
                              <div key={`${file.name}-${file.size}`} className="border rounded-lg p-4">
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
                      <Button onClick={startAnalysis} disabled={processing || files.length < 2} className="gradient-primary text-primary-foreground border-0 hover:opacity-90">
                        {processing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
                        Evaluate with Ollama
                      </Button>
                    </div>
                  </div>
                  <div className="p-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {files.map((file, index) => {
                      const Icon = fileIcon(file.name);
                      return (
                        <div key={`${file.name}-${index}`} className="flex items-center gap-3 p-3 rounded-xl bg-muted/40 group">
                          <div className="h-10 w-10 rounded-lg bg-card flex items-center justify-center"><Icon className="h-5 w-5 text-primary" /></div>
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium truncate">{file.name}</div>
                            <div className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</div>
                          </div>
                          <button onClick={() => setFiles((current) => current.filter((_, i) => i !== index))} className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive" aria-label={`Remove ${file.name}`}>
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
                  <div className="text-sm font-medium mb-4">Evaluating quotations</div>
                  <div className="space-y-3">
                    {steps.map((step) => (
                      <div key={step.key} className="flex items-center gap-3">
                        <div className={cn(
                          "h-7 w-7 rounded-full flex items-center justify-center shrink-0",
                          step.status === "done" && "bg-success text-success-foreground",
                          step.status === "active" && "gradient-primary text-primary-foreground",
                          step.status === "pending" && "bg-muted text-muted-foreground"
                        )}>
                          {step.status === "done" ? <CheckCircle2 className="h-4 w-4" /> :
                            step.status === "active" ? <Loader2 className="h-4 w-4 animate-spin" /> :
                              <span className="text-xs">·</span>}
                        </div>
                        <span className={cn("text-sm", step.status === "pending" && "text-muted-foreground")}>{step.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {!processing && files.length === 0 && (
                <div className="text-center text-sm text-muted-foreground py-12">
                  Quotations are processed by your local backend. No browser-side or synthetic ranking fallback is used.
                </div>
              )}
            </>
          ) : <ResultView result={result} />}
        </div>
      </main>
    </div>
  );
};

function ResultView({ result }: { result: AnalysisResult }) {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className={cn(
        "rounded-2xl p-6 md:p-8 shadow-elevated",
        result.best ? "gradient-primary text-primary-foreground" : "border border-amber-500/40 bg-amber-500/10"
      )}>
        <div className="flex items-center gap-2 text-sm uppercase tracking-wider">
          {result.best ? <Trophy className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
          {result.best ? "AI recommendation" : "Inconclusive evaluation"}
        </div>
        <div className="text-3xl font-bold mt-2">
          {result.best ? result.best.vendor_name ?? "Vendor name not extracted" : "No verified winner"}
        </div>
        <p className="mt-3 text-sm">{result.evaluation_summary}</p>
        {result.alternative && (
          <p className="mt-3 text-sm">
            Alternative to consider: <strong>{result.alternative.vendor_name ?? "Vendor name not extracted"}</strong> (rank #{result.alternative.rank}).
          </p>
        )}
      </div>

      {result.constraint_warnings.map((warning) => (
        <div key={warning} className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm">{warning}</div>
      ))}
      {result.file_errors?.map((fileError) => (
        <div key={`${fileError.name}-${fileError.error}`} className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm">
          Could not process {fileError.name}: {fileError.error}
        </div>
      ))}
      {result.requirements && (
        <div className="rounded-xl border bg-card p-4 text-sm">
          <span className="font-medium">Requirements used:</span> {result.requirements}
        </div>
      )}
      {(result.constraints?.max_budget_inr != null || result.constraints?.max_delivery_days != null) && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 text-sm">
          <strong>Mandatory limits checked:</strong>{" "}
          {[
            result.constraints?.max_budget_inr != null
              ? `Maximum budget ${fmtINR(result.constraints.max_budget_inr)}`
              : null,
            result.constraints?.max_delivery_days != null
              ? `Delivery within ${result.constraints.max_delivery_days} days`
              : null,
          ].filter(Boolean).join(" · ")}
        </div>
      )}

      <div className="grid gap-4">
        {result.vendors.map((vendor) => (
          <VendorCard
            key={vendor.id}
            vendor={vendor}
            isBest={vendor.id === result.best?.id}
            constraints={result.constraints}
          />
        ))}
      </div>
    </div>
  );
}

function VendorCard({
  vendor,
  isBest,
  constraints,
}: {
  vendor: EvaluatedVendor;
  isBest: boolean;
  constraints?: AnalysisResult["constraints"];
}) {
  const budgetStatus = constraintStatus(vendor.total_cost, constraints?.max_budget_inr);
  const deliveryStatus = constraintStatus(vendor.delivery_days, constraints?.max_delivery_days);
  return (
    <article className={cn("rounded-2xl border bg-card shadow-card p-5 space-y-4", isBest && "border-primary/50")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">#{vendor.rank} {vendor.vendor_name ?? "Vendor name not extracted"}</h2>
            {isBest && <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-semibold">Recommended</span>}
            {!isBest && <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{vendor.recommendation_status.replace(/_/g, " ")}</span>}
          </div>
          <p className="text-xs text-muted-foreground mt-1">{vendor.item_name ?? "Item not extracted"} · {vendor.source_file ?? "Quotation file"}</p>
        </div>
        <div className="text-sm text-right">
          <div><strong>Total:</strong> {fmtINR(vendor.total_cost)}</div>
          <div className="text-muted-foreground">Delivery: {vendor.delivery_days == null ? "Unknown" : `${vendor.delivery_days} days`}</div>
          <div className="text-muted-foreground">Payment: {vendor.payment_days == null ? "Unknown" : `Net ${vendor.payment_days} days`}</div>
          {vendor.validity_text && <div className="text-muted-foreground">Validity: {vendor.validity_text}</div>}
        </div>
      </div>

      <div className="grid sm:grid-cols-3 gap-3 text-sm">
        <div className="rounded-lg bg-muted/40 p-3"><div className="font-medium mb-1">Cost comparison</div>{vendor.total_cost == null ? "Total is unavailable; verify the missing quotation amounts." : vendor.cost_comparison}</div>
        <div className="rounded-lg bg-muted/40 p-3"><div className="font-medium mb-1">Delivery</div>{vendor.delivery_comparison}</div>
        <div className="rounded-lg bg-muted/40 p-3"><div className="font-medium mb-1">Payment terms</div>{vendor.payment_terms_comparison}</div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        {[
          ["Base amount", vendor.base_amount == null ? "Unknown" : fmtINR(vendor.base_amount)],
          ["Discount", fmtQuotationAmount(vendor, "discount_amount", vendor.discount_amount)],
          ["Taxable amount", fmtINR(vendor.taxable_amount)],
          ["GST", vendor.gst_percent == null ? "Unknown" : `${vendor.gst_percent}% · ${fmtINR(vendor.gst_amount)}`],
          ["Freight", fmtQuotationAmount(vendor, "freight_cost", vendor.freight)],
          ["Other taxes", fmtQuotationAmount(vendor, "other_taxes", vendor.other_taxes)],
          ["Additional charges", fmtQuotationAmount(vendor, "additional_charges", vendor.additional_charges)],
          ["Quoted total", fmtINR(vendor.quoted_total)],
          ["Calculated total", fmtINR(vendor.calculated_total)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border p-3">
            <div className="text-muted-foreground">{label}</div>
            <div className="font-medium mt-1">{value}</div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        {budgetStatus && <span className="rounded-full border px-2.5 py-1">Budget: {budgetStatus}</span>}
        {deliveryStatus && <span className="rounded-full border px-2.5 py-1">Delivery: {deliveryStatus}</span>}
        {vendor.tax_inclusive != null && <span className="rounded-full border px-2.5 py-1">Tax {vendor.tax_inclusive ? "included" : "excluded"}</span>}
      </div>

      <p className="text-sm">{vendor.explanation}</p>
      <div className="grid md:grid-cols-2 gap-4 text-sm">
        <EvidenceList title="Advantages" items={vendor.advantages} />
        <EvidenceList title="Disadvantages" items={vendor.disadvantages} />
        <EvidenceList title="Risks" items={vendor.risks} />
        <EvidenceList title="Extraction / consistency warnings" items={vendor.data_warnings} />
        <EvidenceList title="Missing information" items={[...vendor.missing_information, ...vendor.missing_fields]} />
        <EvidenceList
          title="Extracted source evidence"
          items={Object.entries(vendor.extraction_evidence ?? {}).map(
            ([field, source]) => `${field} (${vendor.extraction_confidence[field] ?? "unavailable"}): ${source}`
          )}
        />
      </div>
      <div className="rounded-lg border p-3 text-sm">
        <strong>Confidence / uncertainty:</strong> {vendor.confidence_explanation}
      </div>
    </article>
  );
}

function constraintStatus(actual: number | null, limit: number | null | undefined): string | null {
  if (limit == null) return null;
  if (actual == null) return "Needs verification";
  return actual <= limit ? "Meets requirement" : "Does not meet requirement";
}

function EvidenceList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="font-medium mb-1">{title}</h3>
      {items.length ? (
        <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
          {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ul>
      ) : <p className="text-muted-foreground">None identified.</p>}
    </div>
  );
}

function triggerDownload(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default Dashboard;
