import * as XLSX from "xlsx";
import type { AnalysisResult } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function analyzeFiles(
  files: File[],
  requirements: string,
  onStep?: (key: string) => void
): Promise<AnalysisResult> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file, file.name));
  form.append("requirements", requirements);

  onStep?.("read");
  onStep?.("extract");
  onStep?.("evaluate");
  let response: Response;
  try {
    response = await fetch(`${API_BASE.replace(/\/$/, "")}/api/analyze`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new Error("The vendor analysis backend is unavailable. Start the API and Ollama, then retry.");
  }

  if (!response.ok) {
    let detail = `Analysis failed (HTTP ${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail?.message) detail = body.detail.message;
    } catch {
      // Keep the explicit HTTP status when the server response is not JSON.
    }
    throw new Error(detail);
  }

  const result = (await response.json()) as AnalysisResult;
  onStep?.("complete");
  return result;
}

function csvCell(value: unknown): string {
  const text = value == null ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

export function exportToCSV(result: AnalysisResult): string {
  const headers = [
    "Rank", "Vendor", "Recommendation", "Item", "Quoted total (INR)",
    "Calculated total (INR)", "Total cost used (INR)", "Base amount (INR)",
    "GST amount (INR)", "Freight (INR)", "Other taxes (INR)",
    "Additional charges (INR)",
    "Delivery days", "Payment days", "Advantages", "Disadvantages", "Risks",
    "Missing information", "Explanation", "Confidence",
    "Extraction warnings",
  ];
  const rows = result.vendors.map((vendor) => [
    vendor.rank,
    vendor.vendor_name,
    vendor.recommendation_status,
    vendor.item_name,
    vendor.quoted_total,
    vendor.calculated_total,
    vendor.total_cost,
    vendor.base_amount,
    vendor.gst_amount,
    vendor.freight,
    vendor.other_taxes,
    vendor.additional_charges,
    vendor.delivery_days,
    vendor.payment_days,
    vendor.advantages.join("; "),
    vendor.disadvantages.join("; "),
    vendor.risks.join("; "),
    vendor.missing_information.join("; "),
    vendor.explanation,
    vendor.confidence_explanation,
    vendor.data_warnings.join("; "),
  ]);
  return [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
}

export function exportToExcel(result: AnalysisResult): Blob {
  const wb = XLSX.utils.book_new();
  const data = [
    ["Rank", "Vendor", "Recommendation", "Item", "Base (INR)", "Discount (INR)", "Taxable amount (INR)", "GST %", "GST (INR)", "Freight (INR)", "Other taxes (INR)", "Additional charges (INR)", "Quoted total (INR)", "Calculated total (INR)", "Total used for comparison (INR)", "Delivery days", "Payment days", "Advantages", "Disadvantages", "Risks", "Missing information", "Explanation", "Confidence", "Extraction warnings"],
    ...result.vendors.map((vendor) => [
      vendor.rank,
      vendor.vendor_name,
      vendor.recommendation_status,
      vendor.item_name,
      vendor.base_amount,
      vendor.discount_amount,
      vendor.taxable_amount,
      vendor.gst_percent,
      vendor.gst_amount,
      vendor.freight,
      vendor.other_taxes,
      vendor.additional_charges,
      vendor.quoted_total,
      vendor.calculated_total,
      vendor.total_cost,
      vendor.delivery_days,
      vendor.payment_days,
      vendor.advantages.join("; "),
      vendor.disadvantages.join("; "),
      vendor.risks.join("; "),
      vendor.missing_information.join("; "),
      vendor.explanation,
      vendor.confidence_explanation,
      vendor.data_warnings.join("; "),
    ]),
  ];
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(data), "AI Evaluation");
  const out = XLSX.write(wb, { type: "array", bookType: "xlsx" });
  return new Blob([out], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}
