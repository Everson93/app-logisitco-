import { useState } from "react";

import { AlertList } from "../../components/AlertList";
import { KpiCard } from "../../components/KpiCard";
import { Empty, ErrorBox, Loading } from "../../components/Status";
import { useAsync } from "../../components/useAsync";
import { api } from "../../services/api";
import {
  addMonths,
  monthLabel,
  monthRange,
  monthsBetween,
  signedMoney,
  money,
  toNumber,
  unitCost,
} from "../../services/format";
import type { VarianceItem } from "../../types/api";

const REASONS: Record<NonNullable<VarianceItem["reason"]>, string> = {
  MIXED_DRIVERS: "mais de um direcionador",
  NO_BASE_VOLUME: "sem volume no período base",
  NO_CURRENT_VOLUME: "sem volume no período analisado",
};

function tone(value: string | null): "neutral" | "up" | "down" {
  const n = toNumber(value);
  if (n === null || n === 0) return "neutral";
  return n > 0 ? "up" : "down";
}

/**
 * Seção 5.6: separa a variação de custo entre dois meses em efeito volume (o custo mudou
 * porque o volume mudou) e efeito eficiência (o custo por unidade mudou).
 */
export function VariancePanel({
  fromMonth,
  toMonth,
  unitId,
  processId,
}: {
  fromMonth: string;
  toMonth: string;
  unitId: number | null;
  processId: number | null;
}) {
  const options = monthsBetween(addMonths(fromMonth, -1), toMonth);
  const [choice, setChoice] = useState<{ base: string; current: string } | null>(null);
  const defaults = {
    base: fromMonth < toMonth ? fromMonth : addMonths(toMonth, -1),
    current: toMonth,
  };
  // Se o filtro mudou e a escolha saiu do intervalo, volta para o padrão.
  const picked =
    choice && options.includes(choice.base) && options.includes(choice.current) ? choice : defaults;

  const base = monthRange(picked.base, picked.base);
  const current = monthRange(picked.current, picked.current);
  const query = { ...current, unitId, processId };
  const variance = useAsync(
    () => api.variance(query, base.from, base.to),
    [JSON.stringify(query), base.from],
  );
  const v = variance.data;

  return (
    <div className="panel">
      <h2>Variação: volume x eficiência</h2>
      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Comparação">
        <label>
          Mês base
          <select
            value={picked.base}
            onChange={(e) => setChoice({ ...picked, base: e.target.value })}
          >
            {options.map((m) => (
              <option key={m} value={m}>
                {monthLabel(m)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Comparar com
          <select
            value={picked.current}
            onChange={(e) => setChoice({ ...picked, current: e.target.value })}
          >
            {options.map((m) => (
              <option key={m} value={m}>
                {monthLabel(m)}
              </option>
            ))}
          </select>
        </label>
      </form>

      {variance.loading && !v && <Loading />}
      {variance.error && <ErrorBox error={variance.error} onRetry={variance.reload} />}
      {v && (
        <>
          <div className="kpis" aria-label="Decomposição da variação">
            <KpiCard
              label="Variação total"
              value={signedMoney(v.total_change)}
              hint={`${money(v.base_cost)} → ${money(v.actual_cost)}`}
              tone={tone(v.total_change)}
            />
            {/* Sem cor: volume maior não é ineficiência. */}
            <KpiCard
              label="Efeito volume"
              value={signedMoney(v.volume_effect)}
              hint="mudança de volume ao custo unitário base"
            />
            <KpiCard
              label="Efeito eficiência"
              value={signedMoney(v.efficiency_effect)}
              hint="mudança do custo por unidade"
              tone={tone(v.efficiency_effect)}
            />
            {toNumber(v.not_comparable) !== 0 && (
              <KpiCard
                label="Não decomposto"
                value={signedMoney(v.not_comparable)}
                hint="processos sem volume comparável"
              />
            )}
          </div>

          {v.items.length === 0 ? (
            <Empty>Nenhum custo calculado nos dois meses.</Empty>
          ) : (
            <VarianceTable items={v.items} />
          )}
          {v.alerts.length > 0 && <AlertList alerts={v.alerts} />}
          <p className="caption">
            Efeito volume = volume atual × custo unitário base − custo base. Efeito eficiência =
            custo atual − custo esperado no volume atual. A decomposição vale quando o mix de
            unidades e cargas é comparável entre os meses.
          </p>
        </>
      )}
    </div>
  );
}

function VarianceTable({ items }: { items: VarianceItem[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Processo</th>
            <th className="num">Custo base</th>
            <th className="num">Custo atual</th>
            <th className="num">Unitário base → atual</th>
            <th className="num">Efeito volume</th>
            <th className="num">Efeito eficiência</th>
            <th className="num">Variação</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.process_id ?? "none"}>
              <td>{i.process_name}</td>
              <td className="num">{money(i.base_cost)}</td>
              <td className="num">{money(i.actual_cost)}</td>
              {i.comparable ? (
                <>
                  <td className="num">
                    {unitCost(i.base_unit_cost)} → {unitCost(i.actual_unit_cost, i.driver_uom)}
                  </td>
                  <td className="num">{signedMoney(i.volume_effect)}</td>
                  <td className="num">{signedMoney(i.efficiency_effect)}</td>
                </>
              ) : (
                <td className="num muted" colSpan={3}>
                  N/D: {i.reason ? REASONS[i.reason] : "sem dados"}
                </td>
              )}
              <td className="num">{signedMoney(i.total_change)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
