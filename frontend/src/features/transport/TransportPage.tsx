import { useState } from "react";

import { AlertList } from "../../components/AlertList";
import { KpiCard } from "../../components/KpiCard";
import { ErrorBox, Loading } from "../../components/Status";
import { useAsync } from "../../components/useAsync";
import { api } from "../../services/api";
import {
  money,
  monthLabel,
  monthRange,
  percent,
  quantity,
  toNumber,
  unitCost,
} from "../../services/format";
import type { Dimensions, TransportIndicators } from "../../types/api";
import { defaultFilters } from "../dashboard/Filters";

function share(part: string, total: string): string | undefined {
  const p = toNumber(part);
  const t = toNumber(total);
  if (p === null || !t) return undefined;
  return `${Math.round((p / t) * 100)}%`;
}

/** Seção 5.7: custo por viagem, km e palete, ocupação e frota própria x frete terceirizado. */
export function TransportPage({ dimensions }: { dimensions: Dimensions | null }) {
  const initial = defaultFilters();
  const [filters, setFilters] = useState({
    fromMonth: initial.fromMonth,
    toMonth: initial.toMonth,
    unitId: null as number | null,
  });
  const query = { ...monthRange(filters.fromMonth, filters.toMonth), unitId: filters.unitId };
  const data = useAsync(() => api.transport(query), [JSON.stringify(query)]);
  const t = data.data;

  return (
    <section aria-labelledby="transport-title">
      <header className="page-header">
        <h1 id="transport-title">Transporte</h1>
      </header>

      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filtros">
        <label>
          De
          <input
            type="month"
            value={filters.fromMonth}
            max={filters.toMonth}
            onChange={(e) => e.target.value && setFilters({ ...filters, fromMonth: e.target.value })}
          />
        </label>
        <label>
          Até
          <input
            type="month"
            value={filters.toMonth}
            min={filters.fromMonth}
            onChange={(e) => e.target.value && setFilters({ ...filters, toMonth: e.target.value })}
          />
        </label>
        <label>
          Unidade
          <select
            value={filters.unitId ?? ""}
            onChange={(e) =>
              setFilters({ ...filters, unitId: e.target.value ? Number(e.target.value) : null })
            }
          >
            <option value="">Todas</option>
            {dimensions?.units.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </label>
      </form>

      {data.loading && !t && <Loading />}
      {data.error && <ErrorBox error={data.error} onRetry={data.reload} />}
      {t && (
        <>
          <div className="kpis" aria-label="Indicadores de transporte">
            <KpiCard label="Custo de transporte" value={money(t.total_cost)} />
            <KpiCard
              label="Custo por viagem"
              value={unitCost(t.cost_per_trip, "trip")}
              hint={quantity(t.trips, "trip")}
            />
            <KpiCard
              label="Custo por km"
              value={unitCost(t.cost_per_km, "km")}
              hint={`${quantity(t.km, "km")} · ${quantity(t.km_per_trip, "km")} por viagem`}
            />
            <KpiCard
              label="Custo por palete transportado"
              value={unitCost(t.cost_per_pallet, "pallet")}
              hint={quantity(t.pallets, "pallet")}
            />
            <KpiCard
              label="Ocupação"
              value={percent(t.occupancy_percent)}
              hint="paletes transportados / capacidade nominal"
            />
          </div>

          {t.alerts.length > 0 && <AlertList alerts={t.alerts} />}

          <div className="grid-2">
            <div className="panel">
              <h2>Frota própria x frete terceirizado</h2>
              <CostSplit t={t} />
            </div>
            <div className="panel">
              <h2>Como ler</h2>
              <ul className="caption notes">
                <li>O custo inclui o rateio e vem do cálculo vigente de cada mês.</li>
                <li>Km é o total rodado, carregado ou não.</li>
                <li>
                  A capacidade nominal é a soma, por viagem, dos paletes que o veículo comporta.
                </li>
                <li>
                  Frota própria e frete terceirizado são separados pela natureza da conta
                  contábil.
                </li>
              </ul>
            </div>
          </div>

          <div className="panel">
            <h2>Por mês</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Mês</th>
                    <th className="num">Custo</th>
                    <th className="num">Frota própria</th>
                    <th className="num">Frete terceiro</th>
                    <th className="num">Viagens</th>
                    <th className="num">Custo / viagem</th>
                    <th className="num">Custo / km</th>
                    <th className="num">Custo / palete</th>
                    <th className="num">Ocupação</th>
                  </tr>
                </thead>
                <tbody>
                  {t.months.map((m) =>
                    m.calculated ? (
                      <tr key={m.period}>
                        <td className="nowrap">{monthLabel(m.period)}</td>
                        <td className="num">{money(m.total_cost)}</td>
                        <td className="num">{money(m.own_fleet_cost)}</td>
                        <td className="num">{money(m.third_party_cost)}</td>
                        <td className="num">{quantity(m.trips)}</td>
                        <td className="num">{unitCost(m.cost_per_trip)}</td>
                        <td className="num">{unitCost(m.cost_per_km)}</td>
                        <td className="num">{unitCost(m.cost_per_pallet)}</td>
                        <td className="num">{percent(m.occupancy_percent)}</td>
                      </tr>
                    ) : (
                      <tr key={m.period}>
                        <td className="nowrap">{monthLabel(m.period)}</td>
                        <td className="num muted" colSpan={8}>
                          sem cálculo executado
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function CostSplit({ t }: { t: TransportIndicators }) {
  // O percentual é sobre o custo direto; o rateado fica fora da base.
  const rows: [string, string, boolean][] = [
    ["Frota própria", t.own_fleet_cost, true],
    ["Frete terceirizado", t.third_party_cost, true],
    ["Outros custos diretos", t.other_direct_cost, true],
    ["Rateado", t.allocated_cost, false],
  ];
  return (
    <>
      <table>
        <tbody>
        {rows.map(([label, value, direct]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            <td className="num">{money(value)}</td>
            <td className="num muted">
              {direct ? (share(value, t.direct_cost) ?? "") : ""}
            </td>
          </tr>
        ))}
        </tbody>
      </table>
      <p className="caption">Percentuais sobre o custo direto de transporte.</p>
    </>
  );
}
