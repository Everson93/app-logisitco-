import { type FormEvent, useState } from "react";

import { AlertList } from "../../components/AlertList";
import { KpiCard } from "../../components/KpiCard";
import { Empty, ErrorBox } from "../../components/Status";
import { api } from "../../services/api";
import {
  money,
  monthRange,
  quantity,
  signedMoney,
  signedPercent,
  toNumber,
  unitCost,
  uomLabel,
} from "../../services/format";
import type { Dimensions, ScenarioResult } from "../../types/api";
import { defaultFilters } from "../dashboard/Filters";

function tone(value: string | null): "neutral" | "up" | "down" {
  const n = toNumber(value);
  if (n === null || n === 0) return "neutral";
  return n > 0 ? "up" : "down";
}

/** Simulação "e se": nada é gravado, nem execução de cálculo nem regra. */
export function ScenariosPage({ dimensions }: { dimensions: Dimensions | null }) {
  const initial = defaultFilters();
  const [period, setPeriod] = useState({ from: initial.fromMonth, to: initial.toMonth });
  const [volumes, setVolumes] = useState<Record<string, string>>({});
  const [variableShare, setVariableShare] = useState(100);
  const [driver, setDriver] = useState("");
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [running, setRunning] = useState(false);

  async function simulate(e: FormEvent) {
    e.preventDefault();
    setRunning(true);
    setError(null);
    try {
      const range = monthRange(period.from, period.to);
      setResult(
        await api.simulate({
          period_start: range.from,
          period_end: range.to,
          volume_changes: Object.entries(volumes)
            .filter(([, pct]) => pct !== "" && Number(pct) !== 0)
            .map(([process_code, percent]) => ({ process_code, percent })),
          variable_cost_share: String(variableShare / 100),
          allocation_driver_code: driver || null,
        }),
      );
    } catch (err) {
      setError(err as Error);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section aria-labelledby="scen-title">
      <header className="page-header">
        <h1 id="scen-title">Simulação de cenários</h1>
      </header>
      <p className="muted">
        Recalcula o período com as regras atuais e as mudanças abaixo. Nada é gravado: o dashboard
        continua mostrando o cálculo oficial.
      </p>

      <form className="panel scenario-form" onSubmit={simulate} aria-label="Cenário">
        <div className="filters">
          <label>
            De
            <input
              type="month"
              value={period.from}
              max={period.to}
              onChange={(e) => e.target.value && setPeriod({ ...period, from: e.target.value })}
            />
          </label>
          <label>
            Até
            <input
              type="month"
              value={period.to}
              min={period.from}
              onChange={(e) => e.target.value && setPeriod({ ...period, to: e.target.value })}
            />
          </label>
          <label>
            Ratear compartilhados por
            <select value={driver} onChange={(e) => setDriver(e.target.value)}>
              <option value="">Regra atual</option>
              {dimensions?.drivers.map((d) => (
                <option key={d.id} value={d.code}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <h2>Variação de volume por processo</h2>
        <div className="volume-grid">
          {dimensions?.processes.map((p) => (
            <label key={p.id}>
              {p.name}
              <span className="input-suffix">
                <input
                  type="number"
                  inputMode="decimal"
                  step="1"
                  min="-100"
                  max="1000"
                  placeholder="0"
                  aria-label={`Volume de ${p.name} (%)`}
                  value={volumes[p.code] ?? ""}
                  onChange={(e) => setVolumes({ ...volumes, [p.code]: e.target.value })}
                />
                %
              </span>
            </label>
          ))}
        </div>

        <label className="share">
          Parcela variável do custo direto: <strong>{variableShare}%</strong>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={variableShare}
            onChange={(e) => setVariableShare(Number(e.target.value))}
          />
          <span className="caption">
            100% = o custo direto acompanha o volume; 0% = custo fixo. Custos compartilhados não
            mudam, só o rateio deles.
          </span>
        </label>

        <div className="actions">
          <button type="submit" disabled={running}>
            {running ? "Simulando…" : "Simular"}
          </button>
        </div>
      </form>

      {error && <ErrorBox error={error} />}
      {result && <ScenarioResults result={result} />}
    </section>
  );
}

function ScenarioResults({ result }: { result: ScenarioResult }) {
  return (
    <>
      <div className="kpis" aria-label="Resultado do cenário">
        <KpiCard label="Custo atual" value={money(result.base_cost)} />
        <KpiCard label="Custo no cenário" value={money(result.scenario_cost)} />
        <KpiCard
          label="Diferença"
          value={signedMoney(result.change)}
          hint={signedPercent(result.change_percent)}
          tone={tone(result.change)}
        />
        {toNumber(result.scenario_pending) !== 0 && (
          <KpiCard
            label="Pendente no cenário"
            value={money(result.scenario_pending)}
            hint="compartilhado sem rateio"
          />
        )}
      </div>
      {result.alerts.length > 0 && <AlertList alerts={result.alerts} />}

      <div className="panel">
        <h2>Por processo</h2>
        {result.items.length === 0 ? (
          <Empty>Nenhum custo no período escolhido.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Processo</th>
                  <th className="num">Volume</th>
                  <th className="num">Custo atual</th>
                  <th className="num">Custo no cenário</th>
                  <th className="num">Diferença</th>
                  <th className="num">Unitário atual → cenário</th>
                </tr>
              </thead>
              <tbody>
                {result.items.map((i) => (
                  <tr key={i.process_id ?? "none"}>
                    <td>{i.process_name}</td>
                    <td className="num">
                      {quantity(i.scenario_volume, i.driver_uom)}
                      {toNumber(i.volume_change_percent) !== 0 && (
                        <span className="muted"> ({signedPercent(i.volume_change_percent)})</span>
                      )}
                    </td>
                    <td className="num">{money(i.base_cost)}</td>
                    <td className="num">{money(i.scenario_cost)}</td>
                    <td className="num">{signedMoney(i.change)}</td>
                    <td className="num">
                      {unitCost(i.base_unit_cost)} → {unitCost(i.scenario_unit_cost)}
                      {i.driver_uom && ` / ${uomLabel(i.driver_uom, true)}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
