// Contratos da API (backend/app/api/v1). Valores monetários chegam como texto decimal
// para não perder precisão; a conversão para número acontece só na apresentação.

export type Decimal = string;

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown>[] };
}

export interface Unit {
  id: number;
  code: string;
  name: string;
  unit_type: string;
}

export interface Process {
  id: number;
  code: string;
  name: string;
  default_driver_id: number | null;
}

export interface Driver {
  id: number;
  code: string;
  name: string;
  unit_of_measure: string;
}

export interface Dimensions {
  units: Unit[];
  processes: Process[];
  drivers: Driver[];
  accounts: { id: number; code: string; name: string }[];
  cost_centers: { id: number; code: string; name: string }[];
}

export interface DashboardAlert {
  code: string;
  severity: "info" | "warning";
  message: string;
  months?: string[];
}

export interface Indicators {
  actual_cost: Decimal;
  direct_cost: Decimal;
  allocated_cost: Decimal;
  budget_cost: Decimal | null;
  variance_amount: Decimal | null;
  variance_percent: Decimal | null;
  driver_quantity: Decimal | null;
  driver_uom: string | null;
  unit_cost: Decimal | null;
}

export interface Summary extends Indicators {
  period: { from: string; to: string };
  currency: string;
  composition: { direct: Decimal; allocated: Decimal; excluded: Decimal; pending: Decimal };
  calculation_run_ids: number[];
  alerts: DashboardAlert[];
}

export type TrendPoint = { period: string } & (
  | { calculated: false }
  | ({ calculated: true } & Indicators)
);

export interface ProcessItem extends Indicators {
  process_id: number | null;
  process_code: string | null;
  process_name: string;
}

export interface VarianceItem {
  process_id: number | null;
  process_code: string | null;
  process_name: string;
  comparable: boolean;
  reason: "MIXED_DRIVERS" | "NO_BASE_VOLUME" | "NO_CURRENT_VOLUME" | null;
  driver_uom: string | null;
  base_cost: Decimal;
  base_volume: Decimal | null;
  base_unit_cost: Decimal | null;
  actual_cost: Decimal;
  actual_volume: Decimal | null;
  actual_unit_cost: Decimal | null;
  expected_cost: Decimal | null;
  volume_effect: Decimal | null;
  efficiency_effect: Decimal | null;
  total_change: Decimal;
}

export interface Variance {
  base_period: { from: string; to: string };
  period: { from: string; to: string };
  currency: string;
  base_cost: Decimal;
  actual_cost: Decimal;
  total_change: Decimal;
  volume_effect: Decimal;
  efficiency_effect: Decimal;
  not_comparable: Decimal;
  items: VarianceItem[];
  alerts: DashboardAlert[];
}

export interface ScenarioItem {
  process_id: number | null;
  process_code: string | null;
  process_name: string;
  volume_change_percent: Decimal;
  driver_uom: string | null;
  base_cost: Decimal;
  scenario_cost: Decimal;
  change: Decimal;
  change_percent: Decimal | null;
  base_volume: Decimal | null;
  scenario_volume: Decimal | null;
  base_unit_cost: Decimal | null;
  scenario_unit_cost: Decimal | null;
}

export interface ScenarioResult {
  period: { from: string; to: string };
  currency: string;
  base_cost: Decimal;
  scenario_cost: Decimal;
  change: Decimal;
  change_percent: Decimal | null;
  base_pending: Decimal;
  scenario_pending: Decimal;
  items: ScenarioItem[];
  alerts: DashboardAlert[];
}

export interface ScenarioInput {
  period_start: string;
  period_end: string;
  volume_changes: { process_code: string; percent: string }[];
  variable_cost_share: string;
  allocation_driver_code: string | null;
}

export interface CalculationRun {
  id: number;
  period_start: string;
  period_end: string;
  rule_version: string;
  status: string;
  summary: Record<string, unknown> | null;
  created_at: string;
}

export type FileType = "expenses" | "activities" | "budgets";

export interface ImportBatch {
  id: number;
  filename: string;
  file_type: FileType;
  uploaded_by: string | null;
  status: string;
  rows_total: number;
  rows_valid: number;
  rows_rejected: number;
  rows_ignored: number;
  rows_committed: number;
  created_at: string;
  committed_at: string | null;
}

export interface FieldSpec {
  name: string;
  kind: string;
  required: boolean;
}

export interface Preview {
  batch: ImportBatch;
  columns: string[];
  sheets: string[];
  sheet: string | null;
  rows: Record<string, string>[];
  fields: FieldSpec[];
  suggested_mapping: Record<string, string>;
  warnings: string[];
}

export interface ImportIssue {
  row: number;
  column: string | null;
  code: string;
  severity: "error" | "warning";
  message: string;
}

export interface Validation {
  batch: ImportBatch;
  rows_warning: number;
  issues_total: number;
  issues: ImportIssue[];
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface AllocationRule {
  id: number;
  name: string;
  driver_code: string;
  valid_from: string;
  valid_to: string | null;
  scope: Record<string, string[]>;
  priority: number;
  rounding: string;
  active: boolean;
  conflicts_with: number[];
}
