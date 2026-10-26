import type { Dimensions } from "../../types/api";

export interface FilterState {
  fromMonth: string; // AAAA-MM
  toMonth: string;
  unitId: number | null;
  processId: number | null;
}

/** Padrão: os três últimos meses fechados. */
export function defaultFilters(today = new Date()): FilterState {
  const month = (offset: number) => {
    const d = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() + offset, 1));
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
  };
  return { fromMonth: month(-3), toMonth: month(-1), unitId: null, processId: null };
}

export function Filters({
  value,
  onChange,
  dimensions,
}: {
  value: FilterState;
  onChange: (next: FilterState) => void;
  dimensions: Dimensions | null;
}) {
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch });
  const optionalId = (raw: string) => (raw === "" ? null : Number(raw));

  return (
    <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filtros">
      <label>
        De
        <input
          type="month"
          value={value.fromMonth}
          max={value.toMonth}
          onChange={(e) => e.target.value && set({ fromMonth: e.target.value })}
        />
      </label>
      <label>
        Até
        <input
          type="month"
          value={value.toMonth}
          min={value.fromMonth}
          onChange={(e) => e.target.value && set({ toMonth: e.target.value })}
        />
      </label>
      <label>
        Unidade
        <select
          value={value.unitId ?? ""}
          onChange={(e) => set({ unitId: optionalId(e.target.value) })}
        >
          <option value="">Todas</option>
          {dimensions?.units.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Processo
        <select
          value={value.processId ?? ""}
          onChange={(e) => set({ processId: optionalId(e.target.value) })}
        >
          <option value="">Todos</option>
          {dimensions?.processes.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="secondary"
        onClick={() => onChange(defaultFilters())}
        aria-label="Limpar filtros"
      >
        Limpar filtros
      </button>
    </form>
  );
}
