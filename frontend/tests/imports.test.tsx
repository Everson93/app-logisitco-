import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ImportsPage } from "../src/features/imports/ImportsPage";
import type { Preview } from "../src/types/api";

const batch = {
  id: 7,
  filename: "despesas.csv",
  file_type: "expenses" as const,
  uploaded_by: "demo",
  status: "uploaded",
  rows_total: 2,
  rows_valid: 0,
  rows_rejected: 0,
  rows_ignored: 0,
  rows_committed: 0,
  created_at: "2026-10-26T12:00:00Z",
  committed_at: null,
};

const preview: Preview = {
  batch,
  columns: ["Data", "Valor", "Natureza", "Documento"],
  sheets: [],
  sheet: null,
  rows: [{ Data: "30/09/2026", Valor: "10,00", Natureza: "direct", Documento: "NF-1" }],
  fields: [
    { name: "competence_date", kind: "date", required: true },
    { name: "unit_code", kind: "code", required: false },
    { name: "amount", kind: "money", required: true },
    { name: "nature", kind: "code", required: true },
    { name: "source_key", kind: "text", required: true },
  ],
  suggested_mapping: { competence_date: "Data", nature: "Natureza", source_key: "Documento" },
  warnings: [],
};

afterEach(() => vi.unstubAllGlobals());

test("validação exige os campos obrigatórios mapeados e envia a convenção escolhida", async () => {
  const requests: { url: string; body?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      requests.push({ url, body: typeof init?.body === "string" ? init.body : undefined });
      if (url.includes("/preview")) return new Response(JSON.stringify(preview), { status: 201 });
      if (url.includes("/validate"))
        return new Response(
          JSON.stringify({
            batch: { ...batch, status: "ready", rows_valid: 1, rows_rejected: 1 },
            rows_warning: 0,
            issues_total: 1,
            issues: [
              { row: 3, column: "Valor", code: "INVALID_NUMBER", severity: "error", message: "Valor inválido." },
            ],
          }),
          { status: 200 },
        );
      return new Response(JSON.stringify({ items: [], page: 1, page_size: 10, total: 0 }), {
        status: 200,
      });
    }),
  );

  render(<ImportsPage />);
  const file = new File(["x"], "despesas.csv", { type: "text/csv" });
  await userEvent.upload(screen.getByLabelText("Arquivo CSV ou XLSX"), file);
  await userEvent.click(screen.getByRole("button", { name: "Ver prévia" }));

  const validateButton = await screen.findByRole("button", { name: "Validar" });
  expect(validateButton).toBeDisabled();
  expect(screen.getByText(/Mapeie ou informe um valor fixo para: amount/)).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Coluna para amount"), "Valor");
  await userEvent.type(screen.getByLabelText("Valor fixo para unit_code"), "CD-DEMO-01");
  await userEvent.selectOptions(screen.getByLabelText("Formato das datas digitadas"), "dmy");
  await userEvent.selectOptions(screen.getByLabelText("Separador decimal"), ",");
  await userEvent.click(validateButton);

  expect(await screen.findByText("Valor inválido.")).toBeInTheDocument();
  const sent = JSON.parse(requests.find((r) => r.url.includes("/validate"))!.body!);
  expect(sent).toEqual({
    mapping: { competence_date: "Data", nature: "Natureza", source_key: "Documento", amount: "Valor" },
    defaults: { unit_code: "CD-DEMO-01" },
    date_format: "dmy",
    decimal_separator: ",",
  });
  expect(screen.getByRole("button", { name: /Confirmar importação de 1 linha/ })).toBeEnabled();
});
