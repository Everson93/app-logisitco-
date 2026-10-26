import type {
  AllocationRule,
  CalculationRun,
  DimensionItem,
  DimensionKind,
  Dimensions,
  FileType,
  ImportBatch,
  Page,
  Preview,
  ProcessItem,
  ScenarioInput,
  ScenarioResult,
  Summary,
  TrendPoint,
  Transport,
  Validation,
  Variance,
  Warehouse,
} from "../types/api";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown>[] = [],
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Não foi possível falar com o servidor.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `Erro ${response.status} ao chamar o servidor.`,
      error?.details ?? [],
    );
  }
  return (await response.json()) as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export interface DashboardFilters {
  from: string;
  to: string;
  unitId?: number | null;
  processId?: number | null;
}

export function filterQuery(f: DashboardFilters, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams({ from: f.from, to: f.to, ...extra });
  if (f.unitId != null) params.set("unit_id", String(f.unitId));
  if (f.processId != null) params.set("process_id", String(f.processId));
  return params.toString();
}

export const api = {
  dimensions: () => request<Dimensions>("/dimensions"),

  summary: (f: DashboardFilters) => request<Summary>(`/dashboard/summary?${filterQuery(f)}`),
  trend: (f: DashboardFilters) => request<TrendPoint[]>(`/dashboard/trend?${filterQuery(f)}`),
  byProcess: (f: DashboardFilters) =>
    request<ProcessItem[]>(`/dashboard/by-process?${filterQuery(f)}`),
  variance: (f: DashboardFilters, baseFrom: string, baseTo: string) =>
    request<Variance>(
      `/dashboard/variance?${filterQuery(f, { base_from: baseFrom, base_to: baseTo })}`,
    ),
  transport: (f: DashboardFilters) =>
    request<Transport>(`/dashboard/transport?${filterQuery(f)}`),
  warehouse: (f: DashboardFilters) =>
    request<Warehouse>(`/dashboard/warehouse?${filterQuery(f)}`),
  reportUrl: (f: DashboardFilters) => `${BASE}/reports/costs.csv?${filterQuery(f)}`,

  runCalculation: (periodStart: string, periodEnd: string) =>
    request<CalculationRun>(
      "/calculations/run",
      json("POST", { period_start: periodStart, period_end: periodEnd }),
    ),
  simulate: (body: ScenarioInput) =>
    request<ScenarioResult>("/scenarios/simulate", json("POST", body)),
  runs: () => request<Page<CalculationRun>>("/calculations?page_size=10"),

  preview: (file: File, fileType: FileType, sheet?: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("file_type", fileType);
    if (sheet) form.append("sheet", sheet);
    return request<Preview>("/imports/preview", { method: "POST", body: form });
  },
  validate: (
    batchId: number,
    body: {
      mapping: Record<string, string>;
      defaults: Record<string, string>;
      date_format: "iso" | "dmy";
      decimal_separator: "." | ",";
    },
  ) => request<Validation>(`/imports/${batchId}/validate`, json("POST", body)),
  commit: (batchId: number) => request<ImportBatch>(`/imports/${batchId}/commit`, json("POST", {})),
  batches: (page = 1) => request<Page<ImportBatch>>(`/imports?page=${page}&page_size=10`),

  dimensionItems: (kind: DimensionKind) => request<DimensionItem[]>(`/dimensions/${kind}`),
  createDimension: (kind: DimensionKind, body: Record<string, unknown>) =>
    request<DimensionItem>(`/dimensions/${kind}`, json("POST", body)),
  updateDimension: (kind: DimensionKind, id: number, body: Record<string, unknown>) =>
    request<DimensionItem>(`/dimensions/${kind}/${id}`, json("PATCH", body)),
  rules: () => request<AllocationRule[]>("/allocation-rules"),
  createRule: (body: {
    name: string;
    driver_code: string;
    valid_from: string;
    valid_to?: string | null;
    priority: number;
    scope: Record<string, string[]>;
  }) => request<AllocationRule>("/allocation-rules", json("POST", body)),
  setRuleActive: (id: number, active: boolean) =>
    request<AllocationRule>(`/allocation-rules/${id}`, json("PATCH", { active })),
};
