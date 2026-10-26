import { useState } from "react";

import { AlertList } from "../../components/AlertList";
import { KpiCard } from "../../components/KpiCard";
import { Empty, ErrorBox, Loading, Success } from "../../components/Status";
import { useAsync } from "../../components/useAsync";
import { api, type DashboardFilters } from "../../services/api";
import {
  money,
  monthRange,
  quantity,
  signedMoney,
  signedPercent,
  toNumber,
  unitCost,
  varianceLabel,
} from "../../services/format";
import type { Dimensions, ProcessItem } from "../../types/api";
import { ProcessChart, TrendChart } from "./Charts";
import { defaultFilters, Filters, type FilterState } from "./Filters";

function tone(value: string | null): "neutral" | "up" | "down" {
  const n = toNumber(value);
  if (n === null || n === 0) return "neutral";
  return n > 0 ? "up" : "down";
}

export function DashboardPage({ dimensions }: { dimensions: Dimensions | null }) {
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<Error | null>(null);

  const range = monthRange(filters.fromMonth, filters.toMonth);
  const query: DashboardFilters = { ...range, unitId: filters.unitId, processId: filters.processId };
  const key = JSON.stringify(query);

  const summary = useAsync(() => api.summary(query), [key]);
  const trend = useAsync(() => api.trend(query), [key]);
  const byProcess = useAsync(() => api.byProcess(query), [key]);

  async function runCalculation() {
    setRunning(true);
    setRunMessage(null);
    setRunError(null);
    try {
      const run = await api.runCalculation(range.from, range.to);
      setRunMessage(
        run.status === "completed"
          ? `Cálculo ${run.id} concluído.`
          : `Cálculo ${run.id} concluído com pendências.`,
      );
      summary.reload();
      trend.reload();
      byProcess.reload();
    } catch (err) {
      setRunError(err as Error);
    } finally {
      setRunning(false);
    }
  }

  const s = summary.data;

  return (
    <section aria-labelledby="dash-title">
      <header className="page-header">
        <h1 id="dash-title">Dashboard de custos</h1>
        <div className="actions">
          <button type="button" onClick={runCalculation} disabled={running}>
            {running ? "Calculando…" : "Executar cálculo do período"}
          </button>
          <a className="button secondary" href={api.reportUrl(query)} download>
            Exportar CSV
          </a>
        </div>
      </header>

      <Filters value={filters} onChange={setFilters} dimensions={dimensions} />
      {runMessage && <Success>{runMessage}</Success>}
      {runError && <ErrorBox error={runError} />}

      {summary.loading && !s && <Loading />}
      {summary.error && <ErrorBox error={summary.error} onRetry={summary.reload} />}
      {s && (
        <>
          <div className="kpis" aria-label="Indicadores">
            <KpiCard label="Custo realizado" value={money(s.actual_cost)} />
            <KpiCard label="Orçamento" value={money(s.budget_cost)} />
            <KpiCard
              label="Desvio (R$)"
              value={signedMoney(s.variance_amount)}
              hint={varianceLabel(s.variance_amount)}
              tone={tone(s.variance_amount)}
            />
            <KpiCard
              label="Desvio (%)"
              value={signedPercent(s.variance_percent)}
              hint={s.variance_percent === null && s.budget_cost !== null ? "sem base orçamentária" : undefined}
              tone={tone(s.variance_percent)}
            />
            <KpiCard
              label="Custo unitário"
              value={unitCost(s.unit_cost, s.driver_uom)}
              hint={s.unit_cost === null ? "filtre por um processo" : undefined}
            />
            <KpiCard label="Volume do direcionador" value={quantity(s.driver_quantity, s.driver_uom)} />
          </div>

          <div className="grid-2">
            <div className="panel">
              <h2>Tendência mensal</h2>
              {trend.error && <ErrorBox error={trend.error} onRetry={trend.reload} />}
              {trend.data && <TrendChart points={trend.data} />}
              <p className="caption">
                Fonte: execução(ões) de cálculo {s.calculation_run_ids.join(", ") || "—"}. Meses sem
                cálculo ficam em branco.
              </p>
            </div>
            <div className="panel">
              <h2>Custo por processo</h2>
              {byProcess.error && <ErrorBox error={byProcess.error} onRetry={byProcess.reload} />}
              {byProcess.data?.length === 0 && <Empty>Nenhum custo calculado no recorte.</Empty>}
              {byProcess.data && byProcess.data.length > 0 && (
                <ProcessChart items={byProcess.data} />
              )}
            </div>
          </div>

          <div className="grid-2">
            <div className="panel">
              <h2>Composição do custo</h2>
              <table>
                <tbody>
                  <tr>
                    <th scope="row">Custos diretos</th>
                    <td className="num">{money(s.composition.direct)}</td>
                  </tr>
                  <tr>
                    <th scope="row">Custos rateados</th>
                    <td className="num">{money(s.composition.allocated)}</td>
                  </tr>
                  <tr>
                    <th scope="row">Excluídos (fora do custo)</th>
                    <td className="num">{money(s.composition.excluded)}</td>
                  </tr>
                  <tr>
                    <th scope="row">Pendentes de rateio ou classificação</th>
                    <td className="num">{money(s.composition.pending)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="panel">
              <h2>Alertas</h2>
              <AlertList alerts={s.alerts} />
            </div>
          </div>

          {byProcess.data && byProcess.data.length > 0 && (
            <div className="panel">
              <h2>Detalhe por processo</h2>
              <ProcessTable items={byProcess.data} />
            </div>
          )}
        </>
      )}
    </section>
  );
}

function ProcessTable({ items }: { items: ProcessItem[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Processo</th>
            <th className="num">Realizado</th>
            <th className="num">Orçamento</th>
            <th className="num">Desvio</th>
            <th className="num">Desvio %</th>
            <th className="num">Volume</th>
            <th className="num">Custo unitário</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.process_id ?? "none"}>
              <td>{i.process_name}</td>
              <td className="num">{money(i.actual_cost)}</td>
              <td className="num">{money(i.budget_cost)}</td>
              <td className="num">{signedMoney(i.variance_amount)}</td>
              <td className="num">{signedPercent(i.variance_percent)}</td>
              <td className="num">{quantity(i.driver_quantity, i.driver_uom)}</td>
              <td className="num">{unitCost(i.unit_cost, i.driver_uom)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
