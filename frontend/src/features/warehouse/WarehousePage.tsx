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
  ND,
  perHour,
  quantity,
  uomLabel,
  unitCost,
} from "../../services/format";
import type { Dimensions, WarehouseMonth, WarehouseProcess } from "../../types/api";
import { defaultFilters } from "../dashboard/Filters";

/** Seção 5.8: custo unitário direto e rateado, produtividade por hora e linhas no picking. */
export function WarehousePage({ dimensions }: { dimensions: Dimensions | null }) {
  const initial = defaultFilters();
  const [filters, setFilters] = useState({
    fromMonth: initial.fromMonth,
    toMonth: initial.toMonth,
    unitId: null as number | null,
  });
  const query = { ...monthRange(filters.fromMonth, filters.toMonth), unitId: filters.unitId };
  const data = useAsync(() => api.warehouse(query), [JSON.stringify(query)]);
  const w = data.data;
  const pick = w?.items.find((i) => i.process_code === "PICK");

  return (
    <section aria-labelledby="warehouse-title">
      <header className="page-header">
        <h1 id="warehouse-title">Armazém e picking</h1>
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

      {data.loading && !w && <Loading />}
      {data.error && <ErrorBox error={data.error} onRetry={data.reload} />}
      {w && (
        <>
          <div className="kpis" aria-label="Indicadores de picking">
            <KpiCard
              label="Picking: custo por pedido"
              value={unitCost(pick?.unit_cost, "order")}
              hint={pick ? quantity(pick.volume, "order") : undefined}
            />
            <KpiCard
              label="Pedidos por hora"
              value={perHour(pick?.productivity_per_hour)}
              hint={pick ? quantity(pick.productive_hours, "hour") : undefined}
            />
            <KpiCard label="Linhas por hora" value={perHour(pick?.lines_per_hour)} />
            <KpiCard
              label="Linhas por pedido"
              value={quantity(pick?.lines_per_order)}
              hint={pick ? quantity(pick.lines, "line") : undefined}
            />
            <KpiCard label="Picking: custo por hora" value={money(pick?.cost_per_hour)} />
          </div>

          {w.alerts.length > 0 && <AlertList alerts={w.alerts} />}

          <div className="panel">
            <h2>Por processo</h2>
            <ProcessTable items={w.items} />
            <p className="caption">
              Produtividade e custo por hora usam só as unidades e meses com horas apontadas.
            </p>
          </div>

          <div className="panel">
            <h2>Produtividade por mês</h2>
            <MonthTable items={w.items} />
          </div>
        </>
      )}
    </section>
  );
}

function ProcessTable({ items }: { items: WarehouseProcess[] }) {
  if (items.length === 0) return <p className="muted">Sem resultados no período.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Processo</th>
            <th className="num">Custo</th>
            <th className="num">Custo unitário</th>
            <th className="num">Direto</th>
            <th className="num">Rateado</th>
            <th className="num">Horas</th>
            <th className="num">Produtividade</th>
            <th className="num">Custo / hora</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.process_id}>
              <th scope="row">
                {i.process_code} · {i.process_name}
              </th>
              <td className="num">{money(i.total_cost)}</td>
              <td className="num nowrap">{unitCost(i.unit_cost, i.driver_uom)}</td>
              <td className="num">{unitCost(i.direct_unit_cost)}</td>
              <td className="num">{unitCost(i.allocated_unit_cost)}</td>
              <td className="num">{quantity(i.productive_hours)}</td>
              <td className="num nowrap">{perHour(i.productivity_per_hour, i.driver_uom)}</td>
              <td className="num">{money(i.cost_per_hour)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function monthValue(m: WarehouseMonth, key: "productivity_per_hour" | "lines_per_hour") {
  return m.calculated ? quantity(m[key]) : ND;
}

function MonthTable({ items }: { items: WarehouseProcess[] }) {
  const months = items[0]?.months.map((m) => m.period) ?? [];
  if (months.length === 0) return <p className="muted">Sem resultados no período.</p>;
  const pick = items.find((i) => i.process_code === "PICK");
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Mês</th>
            {items.map((i) => (
              <th key={i.process_id} className="num">
                {i.process_code}
                {i.driver_uom && <span className="muted"> ({uomLabel(i.driver_uom)} / h)</span>}
              </th>
            ))}
            {pick && <th className="num">PICK (linhas / h)</th>}
          </tr>
        </thead>
        <tbody>
          {months.map((period, index) => (
            <tr key={period}>
              <td className="nowrap">{monthLabel(period)}</td>
              {items.map((i) => (
                <td key={i.process_id} className="num">
                  {monthValue(i.months[index], "productivity_per_hour")}
                </td>
              ))}
              {pick && <td className="num">{monthValue(pick.months[index], "lines_per_hour")}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
