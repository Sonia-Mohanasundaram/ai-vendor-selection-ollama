export interface VendorRow {
  id: string;
  vendor_id: string;
  vendor_name: string | null;
  item_name: string | null;
  quantity: number | null;
  unit_price: number | null;
  base_amount: number | null;
  quoted_subtotal: number | null;
  discount_amount: number | null;
  taxable_amount: number | null;
  gst_percent: number | null;
  gst_amount: number | null;
  freight: number | null;
  other_taxes: number | null;
  additional_charges: number | null;
  total_cost: number | null;
  quoted_total: number | null;
  calculated_total: number | null;
  total_consistent: boolean | null;
  calculation_basis: string | null;
  currency: string | null;
  tax_inclusive: boolean | null;
  delivery_days: number | null;
  delivery_text: string | null;
  delivery_reliability: string | null;
  payment_days: number | null;
  payment_terms_text: string | null;
  validity_text: string | null;
  source_file: string | null;
  missing_fields: string[];
  data_warnings: string[];
  extraction_evidence: Record<string, string>;
  extraction_confidence: Record<string, "source-backed" | "heuristic" | "calculated" | "unavailable">;
  field_status: Record<string, "source_backed" | "calculated" | "not_provided" | "unknown" | "not_applicable">;
}

export interface EvaluatedVendor extends VendorRow {
  rank: number;
  recommendation_status: "recommended" | "alternative" | "not_recommended" | "inconclusive";
  advantages: string[];
  disadvantages: string[];
  cost_comparison: string;
  delivery_comparison: string;
  payment_terms_comparison: string;
  risks: string[];
  missing_information: string[];
  explanation: string;
  confidence_explanation: string;
}

export interface FileMeta {
  name: string;
  size: number;
  type: string;
  sha256?: string;
}

export interface AnalysisResult {
  id: string;
  title: string;
  createdAt: number;
  vendors: EvaluatedVendor[];
  best: EvaluatedVendor | null;
  alternative: EvaluatedVendor | null;
  inconclusive: boolean;
  evaluation_summary: string;
  requirements: string;
  constraints?: {
    max_budget_inr: number | null;
    max_delivery_days: number | null;
  };
  constraint_warnings: string[];
  explanation: string[];
  file_errors?: { name: string; error: string }[];
  files: FileMeta[];
  output_files?: FileMeta[];
}

export interface ProcessingStep {
  key: string;
  label: string;
  status: "pending" | "active" | "done";
}
