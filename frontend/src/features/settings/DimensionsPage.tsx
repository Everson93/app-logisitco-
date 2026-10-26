import { type FormEvent, useState } from "react";

import { Empty, ErrorBox, Loading } from "../../components/Status";
import { useAsync } from "../../components/useAsync";
import { ApiError, api } from "../../services/api";
import { uomLabel } from "../../services/format";
import type { DimensionItem, DimensionKind } from "../../types/api";

const KINDS: { id: DimensionKind; label: string }[] = [
  { id: "units", label: "Unidades" },
  { id: "processes", label: "Processos" },
  { id: "drivers", label: "Direcionadores" },
  { id: "accounts", label: "Contas" },
  { id: "cost-centers", label: "Centros de custo" },
];

const UNIT_TYPES: Record<string, string> = {
  distribution_center: "Centro de distribuição",
  store: "Loja",
};

const COST_NATURES: Record<string, string> = {
  fleet_own: "Frota própria",
  freight_third_party: "Frete terceirizado",
};

type Form = Record<string, string>;

function emptyForm(kind: DimensionKind): Form {
  const base = { code: "", name: "" };
  if (kind === "units") return { ...base, unit_type: "distribution_center" };
  if (kind === "drivers") return { ...base, unit_of_measure: "" };
  if (kind === "processes") return { ...base, default_driver_code: "" };
  if (kind === "accounts") return { ...base, cost_nature: "" };
  return { ...base, unit_code: "" };
}

function formFrom(kind: DimensionKind, item: DimensionItem): Form {
  const form = emptyForm(kind);
  for (const key of Object.keys(form)) {
    form[key] = String(item[key as keyof DimensionItem] ?? "");
  }
  return form;
}

/** Corpo da requisição: texto vazio vira null nos campos opcionais. */
function body(form: Form, editing: boolean): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(form)) {
    // Código e unidade de medida não mudam depois de criados.
    if (editing && (key === "code" || key === "unit_of_measure")) continue;
    out[key] = value === "" && key !== "name" ? null : value;
  }
  return out;
}

function errorText(error: Error): string {
  if (!(error instanceof ApiError) || error.details.length === 0) return error.message;
  const items = error.details.map((d) => [d.field, d.value, d.code].filter(Boolean).join(" · "));
  return `${error.message} (${items.join("; ")})`;
}

/** Seção 11.4: cadastros. Nada é apagado; um registro sai de uso ao ser desativado. */
export function DimensionsPage({ onChanged }: { onChanged?: () => void }) {
  const [kind, setKind] = useState<DimensionKind>("units");
  const items = useAsync(() => api.dimensionItems(kind), [kind]);
  const drivers = useAsync(() => api.dimensionItems("drivers"), []);
  const units = useAsync(() => api.dimensionItems("units"), []);
  const [form, setForm] = useState<Form>(emptyForm("units"));
  const [editing, setEditing] = useState<DimensionItem | null>(null);
  const [error, setError] = useState<Error | null>(null);

  function choose(next: DimensionKind) {
    setKind(next);
    setForm(emptyForm(next));
    setEditing(null);
    setError(null);
  }

  function reloadAll() {
    items.reload();
    if (kind === "drivers") drivers.reload();
    if (kind === "units") units.reload();
    onChanged?.();
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (editing) await api.updateDimension(kind, editing.id, body(form, true));
      else await api.createDimension(kind, body(form, false));
      setForm(emptyForm(kind));
      setEditing(null);
      reloadAll();
    } catch (err) {
      setError(err as Error);
    }
  }

  async function toggle(item: DimensionItem) {
    setError(null);
    try {
      await api.updateDimension(kind, item.id, { active: !item.active });
      reloadAll();
    } catch (err) {
      setError(err as Error);
    }
  }

  const label = KINDS.find((k) => k.id === kind)?.label ?? kind;
  const activeDrivers = drivers.data?.filter((d) => d.active) ?? [];
  const activeUnits = units.data?.filter((u) => u.active) ?? [];

  return (
    <section aria-labelledby="dimensions-title">
      <header className="page-header">
        <h1 id="dimensions-title">Cadastros</h1>
      </header>
      <p className="muted">
        O código é a chave usada na importação e não muda depois de criado. Nada é apagado: um
        cadastro desativado deixa de ser aceito em novas importações e some dos filtros, mas o
        histórico continua.
      </p>

      <div className="segmented" role="group" aria-label="Tipo de cadastro">
        {KINDS.map((k) => (
          <button
            key={k.id}
            type="button"
            aria-pressed={kind === k.id}
            className={kind === k.id ? "secondary active" : "secondary"}
            onClick={() => choose(k.id)}
          >
            {k.label}
          </button>
        ))}
      </div>

      {error && <div className="status status-error" role="alert">{errorText(error)}</div>}

      <div className="panel">
        <h2>{label}</h2>
        {items.loading && !items.data && <Loading />}
        {items.error && <ErrorBox error={items.error} onRetry={items.reload} />}
        {items.data?.length === 0 && <Empty>Nenhum cadastro.</Empty>}
        {items.data && items.data.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Nome</th>
                  <DetailHeader kind={kind} />
                  <th>Situação</th>
                  <th>
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.data.map((item) => (
                  <tr key={item.id} className={item.active ? undefined : "muted"}>
                    <td className="nowrap">{item.code}</td>
                    <td>{item.name}</td>
                    <DetailCell kind={kind} item={item} />
                    <td>
                      <button type="button" className="secondary" onClick={() => toggle(item)}>
                        {item.active ? "Ativo · desativar" : "Inativo · ativar"}
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="link"
                        aria-label={`Editar ${item.code}`}
                        onClick={() => {
                          setEditing(item);
                          setForm(formFrom(kind, item));
                          setError(null);
                        }}
                      >
                        Editar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <form className="panel" onSubmit={save} aria-label="Formulário de cadastro">
        <h2>{editing ? `Editar ${editing.code}` : "Novo cadastro"}</h2>
        <div className="form-row">
          <label>
            Código
            <input
              required
              disabled={editing !== null}
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
            />
          </label>
          <label>
            Nome
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          {kind === "units" && (
            <label>
              Tipo
              <select
                value={form.unit_type}
                onChange={(e) => setForm({ ...form, unit_type: e.target.value })}
              >
                {Object.entries(UNIT_TYPES).map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
            </label>
          )}
          {kind === "drivers" && (
            <label>
              Unidade de medida
              <input
                required
                disabled={editing !== null}
                placeholder="ex.: pallet, order, hour"
                value={form.unit_of_measure}
                onChange={(e) => setForm({ ...form, unit_of_measure: e.target.value })}
              />
            </label>
          )}
          {kind === "processes" && (
            <label>
              Direcionador padrão
              <select
                value={form.default_driver_code}
                onChange={(e) => setForm({ ...form, default_driver_code: e.target.value })}
              >
                <option value="">Nenhum</option>
                {activeDrivers.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.name} ({uomLabel(d.unit_of_measure ?? "")})
                  </option>
                ))}
              </select>
            </label>
          )}
          {kind === "accounts" && (
            <label>
              Natureza
              <select
                value={form.cost_nature}
                onChange={(e) => setForm({ ...form, cost_nature: e.target.value })}
              >
                <option value="">Sem natureza específica</option>
                {Object.entries(COST_NATURES).map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
            </label>
          )}
          {kind === "cost-centers" && (
            <label>
              Unidade
              <select
                value={form.unit_code}
                onChange={(e) => setForm({ ...form, unit_code: e.target.value })}
              >
                <option value="">Nenhuma</option>
                {activeUnits.map((u) => (
                  <option key={u.code} value={u.code}>
                    {u.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <div className="actions">
          <button type="submit">{editing ? "Salvar" : "Criar"}</button>
          {editing && (
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setEditing(null);
                setForm(emptyForm(kind));
              }}
            >
              Cancelar
            </button>
          )}
        </div>
      </form>
    </section>
  );
}

const DETAIL_LABEL: Record<DimensionKind, string> = {
  units: "Tipo",
  processes: "Direcionador padrão",
  drivers: "Unidade de medida",
  accounts: "Natureza",
  "cost-centers": "Unidade",
};

function DetailHeader({ kind }: { kind: DimensionKind }) {
  return <th>{DETAIL_LABEL[kind]}</th>;
}

function DetailCell({ kind, item }: { kind: DimensionKind; item: DimensionItem }) {
  let text: string;
  if (kind === "units") text = UNIT_TYPES[item.unit_type ?? ""] ?? item.unit_type ?? "";
  else if (kind === "processes") text = item.default_driver_code ?? "—";
  else if (kind === "drivers") text = item.unit_of_measure ?? "";
  else if (kind === "accounts") text = item.cost_nature ? COST_NATURES[item.cost_nature] : "—";
  else text = item.unit_code ?? "—";
  return <td>{text}</td>;
}
