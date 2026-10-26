import { type FormEvent, useState } from "react";

import { Empty, ErrorBox, Loading } from "../../components/Status";
import { useAsync } from "../../components/useAsync";
import { api } from "../../services/api";
import { uomLabel } from "../../services/format";
import type { Dimensions } from "../../types/api";

const SCOPE_LABELS: Record<string, string> = {
  source_unit_codes: "Despesas das unidades",
  source_account_codes: "Despesas das contas",
  target_unit_codes: "Destinos: unidades",
  target_process_codes: "Destinos: processos",
};

export function RulesPage({ dimensions }: { dimensions: Dimensions | null }) {
  const rules = useAsync(() => api.rules(), []);
  const [error, setError] = useState<Error | null>(null);
  const [form, setForm] = useState({
    name: "",
    driver_code: "",
    valid_from: "2026-01-01",
    priority: 100,
    source_unit: "",
    target_process: "",
  });

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const scope: Record<string, string[]> = {};
      if (form.source_unit) scope.source_unit_codes = [form.source_unit];
      if (form.target_process) scope.target_process_codes = [form.target_process];
      await api.createRule({
        name: form.name,
        driver_code: form.driver_code,
        valid_from: form.valid_from,
        priority: form.priority,
        scope,
      });
      setForm({ ...form, name: "" });
      rules.reload();
    } catch (err) {
      setError(err as Error);
    }
  }

  async function toggle(id: number, active: boolean) {
    setError(null);
    try {
      await api.setRuleActive(id, active);
      rules.reload();
    } catch (err) {
      setError(err as Error);
    }
  }

  return (
    <section aria-labelledby="rules-title">
      <header className="page-header">
        <h1 id="rules-title">Regras de rateio</h1>
      </header>
      <p className="muted">
        Custos compartilhados só são rateados por uma regra explícita. Sem regra válida, eles ficam
        pendentes no cálculo. Após alterar regras, execute o cálculo de novo no dashboard.
      </p>
      {error && <ErrorBox error={error} />}

      <div className="panel">
        <h2>Regras cadastradas</h2>
        {rules.loading && !rules.data && <Loading />}
        {rules.error && <ErrorBox error={rules.error} onRetry={rules.reload} />}
        {rules.data?.length === 0 && <Empty>Nenhuma regra cadastrada.</Empty>}
        {rules.data && rules.data.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Direcionador</th>
                  <th>Vigência</th>
                  <th>Escopo</th>
                  <th className="num">Prioridade</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {rules.data.map((r) => (
                  <tr key={r.id}>
                    <td>
                      {r.name}
                      {r.conflicts_with.length > 0 && (
                        <div className="alert alert-warning">
                          Conflita com a(s) regra(s) {r.conflicts_with.join(", ")} (mesma
                          prioridade).
                        </div>
                      )}
                    </td>
                    <td>{r.driver_code}</td>
                    <td>
                      {r.valid_from} → {r.valid_to ?? "sem fim"}
                    </td>
                    <td>
                      {Object.keys(r.scope).length === 0
                        ? "Todas as despesas compartilhadas"
                        : Object.entries(r.scope).map(([k, v]) => (
                            <div key={k}>
                              {SCOPE_LABELS[k] ?? k}: {v.join(", ")}
                            </div>
                          ))}
                    </td>
                    <td className="num">{r.priority}</td>
                    <td>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => toggle(r.id, !r.active)}
                      >
                        {r.active ? "Ativa · desativar" : "Inativa · ativar"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <form className="panel" onSubmit={create}>
        <h2>Nova regra</h2>
        <div className="form-row">
          <label>
            Nome
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <label>
            Direcionador
            <select
              required
              value={form.driver_code}
              onChange={(e) => setForm({ ...form, driver_code: e.target.value })}
            >
              <option value="">Escolha…</option>
              {dimensions?.drivers.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name} ({uomLabel(d.unit_of_measure)})
                </option>
              ))}
            </select>
          </label>
          <label>
            Vigente desde
            <input
              type="date"
              required
              value={form.valid_from}
              onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
            />
          </label>
          <label>
            Prioridade (menor vence)
            <input
              type="number"
              min={1}
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
            />
          </label>
          <label>
            Despesas da unidade
            <select
              value={form.source_unit}
              onChange={(e) => setForm({ ...form, source_unit: e.target.value })}
            >
              <option value="">Qualquer</option>
              {dimensions?.units.map((u) => (
                <option key={u.code} value={u.code}>
                  {u.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ratear para o processo
            <select
              value={form.target_process}
              onChange={(e) => setForm({ ...form, target_process: e.target.value })}
            >
              <option value="">Qualquer com volume</option>
              {dimensions?.processes.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button type="submit">Criar regra</button>
      </form>
    </section>
  );
}
