import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { money, monthLabel, toNumber } from "../../services/format";
import type { ProcessItem, TrendPoint } from "../../types/api";

const compact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
const axisMoney = (v: number) => `R$ ${compact.format(v)}`;
const tooltipMoney = (v: unknown) => money(v as number | null);

export function TrendChart({ points }: { points: TrendPoint[] }) {
  const data = points.map((p) => ({
    period: monthLabel(p.period),
    custo: p.calculated ? toNumber(p.actual_cost) : null,
    orcamento: p.calculated ? toNumber(p.budget_cost) : null,
  }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
        <XAxis dataKey="period" tick={{ fontSize: 12 }} />
        <YAxis tickFormatter={axisMoney} width={96} tick={{ fontSize: 12 }} />
        <Tooltip formatter={tooltipMoney} />
        <Legend />
        <Line
          type="monotone"
          dataKey="custo"
          name="Custo realizado"
          stroke="var(--series-1)"
          strokeWidth={2}
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="orcamento"
          name="Orçamento"
          stroke="var(--series-2)"
          strokeWidth={2}
          strokeDasharray="6 4"
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ProcessChart({ items }: { items: ProcessItem[] }) {
  // Eixo com o código (REC, PICK…) para caber; o nome completo aparece no tooltip.
  const names = Object.fromEntries(items.map((i) => [i.process_code ?? "—", i.process_name]));
  const data = items.map((i) => ({
    processo: i.process_code ?? "—",
    custo: toNumber(i.actual_cost),
    orcamento: toNumber(i.budget_cost),
  }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
        <XAxis dataKey="processo" interval={0} tick={{ fontSize: 12 }} />
        <YAxis tickFormatter={axisMoney} width={96} tick={{ fontSize: 12 }} />
        <Tooltip formatter={tooltipMoney} labelFormatter={(code) => names[String(code)] ?? code} />
        <Legend />
        <Bar dataKey="custo" name="Custo realizado" fill="var(--series-1)" />
        <Bar dataKey="orcamento" name="Orçamento" fill="var(--series-2)" />
      </BarChart>
    </ResponsiveContainer>
  );
}
