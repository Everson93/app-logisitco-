import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DashboardPage } from "../src/features/dashboard/DashboardPage";
import type { Dimensions, Summary } from "../src/types/api";

const dims: Dimensions = {
  units: [{ id: 1, code: "CD-DEMO-01", name: "Centro de Distribuição Demo", unit_type: "dc" }],
  processes: [{ id: 10, code: "REC", name: "Recebimento", default_driver_id: 1 }],
  drivers: [],
  accounts: [],
  cost_centers: [],
};

const summary: Summary = {
  period: { from: "2026-09-01", to: "2026-09-30" },
  currency: "BRL",
  actual_cost: "187500.00",
  direct_cost: "180000.00",
  allocated_cost: "7500.00",
  budget_cost: "165000.00",
  variance_amount: "22500.00",
  variance_percent: "13.64",
  driver_quantity: null,
  driver_uom: null,
  unit_cost: null,
  composition: { direct: "180000.00", allocated: "7500.00", excluded: "999.00", pending: "0.00" },
  calculation_run_ids: [3],
  alerts: [{ code: "OVER_BUDGET", severity: "warning", message: "Realizado acima do orçamento." }],
};

function mockFetch() {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const body = url.includes("/summary")
        ? summary
        : url.includes("/trend")
          ? [{ period: "2026-09-01", calculated: false }]
          : [];
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

test("cartões mostram desvio com sinal e N/D quando não há custo unitário", async () => {
  mockFetch();
  render(<DashboardPage dimensions={dims} />);

  const kpis = await screen.findByLabelText("Indicadores");
  expect(within(kpis).getByText(/187\.500,00/)).toBeInTheDocument();
  expect(within(kpis).getByText("+13,64%")).toBeInTheDocument();
  expect(within(kpis).getByText("acima do orçamento")).toBeInTheDocument();
  expect(within(kpis).getAllByText("N/D")).toHaveLength(2); // custo unitário e volume
  expect(screen.getByText("Realizado acima do orçamento.")).toBeInTheDocument();
  expect(screen.getByText("Nenhum custo calculado no recorte.")).toBeInTheDocument();
});

test("filtros chegam à API e podem ser limpos", async () => {
  const calls = mockFetch();
  render(<DashboardPage dimensions={dims} />);
  await screen.findByLabelText("Indicadores");

  await userEvent.selectOptions(screen.getByLabelText("Unidade"), "1");
  await screen.findByLabelText("Indicadores");
  expect(calls.some((c) => c.includes("/summary") && c.includes("unit_id=1"))).toBe(true);
  expect(screen.getByRole("link", { name: "Exportar CSV" })).toHaveAttribute(
    "href",
    expect.stringContaining("unit_id=1"),
  );

  await userEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));
  expect(screen.getByLabelText("Unidade")).toHaveValue("");
});

test("erro da API aparece com opção de tentar de novo", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({ error: { code: "INVALID_PERIOD", message: "Período inválido.", details: [] } }),
          { status: 422 },
        ),
    ),
  );
  render(<DashboardPage dimensions={dims} />);
  const alerts = await screen.findAllByRole("alert");
  expect(alerts[0]).toHaveTextContent("Período inválido.");
  expect(screen.getAllByRole("button", { name: "Tentar de novo" }).length).toBeGreaterThan(0);
});
