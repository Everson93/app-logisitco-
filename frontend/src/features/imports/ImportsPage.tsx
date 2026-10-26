import { useState } from "react";

import { Empty, ErrorBox, Loading, Success } from "../../components/Status";
import { useAsync } from "../../components/useAsync";
import { api } from "../../services/api";
import type { FileType, ImportBatch, Preview, Validation } from "../../types/api";

const FILE_TYPES: { value: FileType; label: string }[] = [
  { value: "expenses", label: "Despesas" },
  { value: "activities", label: "Atividades (volumes)" },
  { value: "budgets", label: "Orçamento" },
];

const STATUS: Record<string, string> = {
  uploaded: "Enviado",
  ready: "Validado",
  failed: "Sem linhas novas",
  committed: "Confirmado",
  cancelled: "Cancelado",
};

type Step = "file" | "mapping" | "result";

export function ImportsPage({ onCommitted }: { onCommitted?: () => void }) {
  const [step, setStep] = useState<Step>("file");
  const [fileType, setFileType] = useState<FileType>("expenses");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [dateFormat, setDateFormat] = useState<"iso" | "dmy">("iso");
  const [decimal, setDecimal] = useState<"." | ",">(".");
  const [validation, setValidation] = useState<Validation | null>(null);
  const [committed, setCommitted] = useState<ImportBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const history = useAsync(() => api.batches(), []);

  async function guard(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  }

  const sendFile = (sheet?: string) =>
    guard(async () => {
      if (!file) return;
      const result = await api.preview(file, fileType, sheet);
      setPreview(result);
      setMapping(result.suggested_mapping);
      setDefaults({});
      setValidation(null);
      setCommitted(null);
      setStep("mapping");
      history.reload();
    });

  const validate = () =>
    guard(async () => {
      if (!preview) return;
      const clean = Object.fromEntries(Object.entries(defaults).filter(([, v]) => v.trim()));
      setValidation(
        await api.validate(preview.batch.id, {
          mapping,
          defaults: clean,
          date_format: dateFormat,
          decimal_separator: decimal,
        }),
      );
    });

  const commit = () =>
    guard(async () => {
      if (!preview) return;
      setCommitted(await api.commit(preview.batch.id));
      setStep("result");
      history.reload();
      onCommitted?.();
    });

  function restart() {
    setStep("file");
    setFile(null);
    setPreview(null);
    setValidation(null);
    setCommitted(null);
    setError(null);
  }

  const missingRequired =
    preview?.fields.filter((f) => f.required && !mapping[f.name] && !defaults[f.name]?.trim()) ?? [];

  return (
    <section aria-labelledby="imp-title">
      <header className="page-header">
        <h1 id="imp-title">Central de importação</h1>
      </header>

      <ol className="steps" aria-label="Etapas">
        <li className={step === "file" ? "current" : "done"}>1. Arquivo</li>
        <li className={step === "mapping" && !validation ? "current" : step === "file" ? "" : "done"}>
          2. Mapeamento
        </li>
        <li className={validation && step === "mapping" ? "current" : step === "result" ? "done" : ""}>
          3. Validação
        </li>
        <li className={step === "result" ? "current" : ""}>4. Confirmação</li>
      </ol>

      {error && <ErrorBox error={error} />}

      {step === "file" && (
        <div className="panel">
          <div className="form-row">
            <label>
              Tipo de arquivo
              <select value={fileType} onChange={(e) => setFileType(e.target.value as FileType)}>
                {FILE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Arquivo CSV ou XLSX
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>
          <button type="button" disabled={!file || busy} onClick={() => sendFile()}>
            {busy ? "Lendo arquivo…" : "Ver prévia"}
          </button>
        </div>
      )}

      {step === "mapping" && preview && (
        <div className="panel">
          <h2>
            {preview.batch.filename} · {preview.batch.rows_total} linhas
          </h2>
          {preview.warnings.map((w) => (
            <p key={w} className="alert alert-warning">
              {w}
            </p>
          ))}
          {preview.sheets.length > 1 && (
            <label>
              Aba
              <select value={preview.sheet ?? ""} onChange={(e) => sendFile(e.target.value)}>
                {preview.sheets.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
          )}

          <div className="form-row">
            <label>
              Formato das datas digitadas
              <select
                value={dateFormat}
                onChange={(e) => setDateFormat(e.target.value as "iso" | "dmy")}
              >
                <option value="iso">AAAA-MM-DD</option>
                <option value="dmy">DD/MM/AAAA</option>
              </select>
            </label>
            <label>
              Separador decimal
              <select value={decimal} onChange={(e) => setDecimal(e.target.value as "." | ",")}>
                <option value=".">Ponto (1234.56)</option>
                <option value=",">Vírgula (1.234,56)</option>
              </select>
            </label>
          </div>

          <div className="table-wrap">
            <table aria-label="Mapeamento de colunas">
              <thead>
                <tr>
                  <th>Campo</th>
                  <th>Coluna do arquivo</th>
                  <th>Ou valor fixo</th>
                </tr>
              </thead>
              <tbody>
                {preview.fields.map((f) => (
                  <tr key={f.name}>
                    <td>
                      <code>{f.name}</code>
                      {f.required && <span className="required"> obrigatório</span>}
                    </td>
                    <td>
                      <select
                        aria-label={`Coluna para ${f.name}`}
                        value={mapping[f.name] ?? ""}
                        onChange={(e) => {
                          const next = { ...mapping };
                          if (e.target.value) next[f.name] = e.target.value;
                          else delete next[f.name];
                          setMapping(next);
                          setValidation(null);
                        }}
                      >
                        <option value="">— não mapear —</option>
                        {preview.columns.map((c) => (
                          <option key={c}>{c}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        aria-label={`Valor fixo para ${f.name}`}
                        disabled={Boolean(mapping[f.name])}
                        value={defaults[f.name] ?? ""}
                        onChange={(e) => {
                          setDefaults({ ...defaults, [f.name]: e.target.value });
                          setValidation(null);
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <details>
            <summary>Amostra do arquivo ({preview.rows.length} primeiras linhas)</summary>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {preview.columns.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, i) => (
                    <tr key={i}>
                      {preview.columns.map((c) => (
                        <td key={c}>{row[c]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          {missingRequired.length > 0 && (
            <p className="alert alert-warning">
              Mapeie ou informe um valor fixo para: {missingRequired.map((f) => f.name).join(", ")}.
            </p>
          )}
          <div className="actions">
            <button type="button" className="secondary" onClick={restart}>
              Cancelar
            </button>
            <button
              type="button"
              disabled={busy || missingRequired.length > 0}
              onClick={validate}
            >
              {busy && !validation ? "Validando…" : "Validar"}
            </button>
          </div>

          {validation && <ValidationResult validation={validation} />}
          {validation && (
            <div className="actions">
              <button
                type="button"
                disabled={busy || validation.batch.status !== "ready"}
                onClick={commit}
              >
                Confirmar importação de {validation.batch.rows_valid - validation.batch.rows_ignored}{" "}
                linha(s)
              </button>
            </div>
          )}
        </div>
      )}

      {step === "result" && committed && (
        <div className="panel">
          <Success>
            Lote {committed.id} confirmado: {committed.rows_committed} linha(s) gravada(s)
            {committed.rows_ignored > 0 && `, ${committed.rows_ignored} já existente(s) ignorada(s)`}
            {committed.rows_rejected > 0 && `, ${committed.rows_rejected} rejeitada(s)`}.
          </Success>
          <button type="button" onClick={restart}>
            Nova importação
          </button>
        </div>
      )}

      <div className="panel">
        <h2>Histórico de lotes</h2>
        {history.loading && !history.data && <Loading />}
        {history.error && <ErrorBox error={history.error} onRetry={history.reload} />}
        {history.data?.items.length === 0 && <Empty>Nenhuma importação ainda.</Empty>}
        {history.data && history.data.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Lote</th>
                  <th>Arquivo</th>
                  <th>Tipo</th>
                  <th>Status</th>
                  <th className="num">Linhas</th>
                  <th className="num">Gravadas</th>
                  <th className="num">Rejeitadas</th>
                  <th>Usuário</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {history.data.items.map((b) => (
                  <tr key={b.id}>
                    <td>{b.id}</td>
                    <td>{b.filename}</td>
                    <td>{FILE_TYPES.find((t) => t.value === b.file_type)?.label}</td>
                    <td>{STATUS[b.status] ?? b.status}</td>
                    <td className="num">{b.rows_total}</td>
                    <td className="num">{b.rows_committed}</td>
                    <td className="num">{b.rows_rejected}</td>
                    <td>{b.uploaded_by}</td>
                    <td>{new Date(b.created_at).toLocaleString("pt-BR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

function ValidationResult({ validation }: { validation: Validation }) {
  const { batch, issues, issues_total } = validation;
  return (
    <div className="validation">
      <p>
        <strong>{batch.rows_valid}</strong> válida(s), <strong>{batch.rows_rejected}</strong>{" "}
        rejeitada(s), <strong>{batch.rows_ignored}</strong> já importada(s),{" "}
        <strong>{validation.rows_warning}</strong> com aviso.
      </p>
      {issues_total > 0 && (
        <div className="table-wrap">
          <table aria-label="Erros e avisos">
            <thead>
              <tr>
                <th className="num">Linha</th>
                <th>Coluna</th>
                <th>Código</th>
                <th>Tipo</th>
                <th>Explicação</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((i, n) => (
                <tr key={n} className={i.severity === "error" ? "row-error" : "row-warning"}>
                  <td className="num">{i.row}</td>
                  <td>{i.column ?? "—"}</td>
                  <td>
                    <code>{i.code}</code>
                  </td>
                  <td>{i.severity === "error" ? "Erro" : "Aviso"}</td>
                  <td>{i.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {issues_total > issues.length && (
            <p className="caption">
              Mostrando {issues.length} de {issues_total}. A lista completa está em{" "}
              <code>/api/v1/imports/{batch.id}/errors</code>.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
