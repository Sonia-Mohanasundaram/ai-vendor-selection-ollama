export interface VendorRow {
  id: string;
  vendor_name: string;
  item_name: string;
  quantity: number;
  unit_price: number;
  base_amount: number;
  gst_pct: number;
  gst_amount: number;
  freight: number;
  delivery_days: number;
  payment_days: number;
  credit_cost: number;
  delay_penalty_cost: number;
  missing_data_risk_cost: number;
  total_cost: number;
  currency: string;
  source_file: string;
}

export interface ScoredVendor extends VendorRow {
  cost_score: number;
  delivery_score: number;
  terms_score: number;
  final_score: number;
  rank: number;
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
  vendors: ScoredVendor[];
  best: ScoredVendor;
  explanation: string[];
  differences: {
    vendor_name: string;
    cost_diff: number;
    delivery_diff: number;
    terms_diff: number;
  }[];
  files: FileMeta[];
  output_files?: FileMeta[];
}

export interface ProcessingStep {
  key: string;
  label: string;
  status: "pending" | "active" | "done";
}
