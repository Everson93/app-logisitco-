import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ScenariosPage } from "../src/features/scenarios/ScenariosPage";
import type { Dimensions, ScenarioResult } from "../src/types/api";

const dims: Dimensions = {
  units: [],
  processes: [
    { id: 10, code: "REC", name: "Recebimento", default_driver_id: 1 },
    { id: 11, code: "PICK", name: "Separação / picking", default_driver_id: 2 },
  ],
  drivers: [
    { id: 1, code: "pallet_received", name: "Palete recebido", unit_of_measure: "pallet" },
    { id: 2, code: "order_picked", name: "Pedido separado", unit_of_measure: "order" },
  ],
  accounts: [],
  cost_centers: [],
};

const result: ScenarioResult = {
  period: { from: "2026-09-01", to: "2026-09-30" },
  currency: "BRL",
  base_cost: "160000.00",
  scenario_cost: "170000.00",
  change: "10000.00",
  change_percent: "6.25",
  base_pending: "0.00",
  scenario_pending: "0.00",
  items: [
    {
      process_id: 10,
      process_code: "REC",
      process_name: "Recebimento",
      volume_change_percent: "20",
      driver_uom: "pallet",
      base_cost: "110000.00",
      scenario_cost: "120000.00",
      change: "10000.00",
      change_percent: "9.09",
      base_volume: "10000",
      scenario_volume: "12000",
      base_unit_cost: "11.0000",
      scenario_unit_cost: "10.0000",
    },
  ],
  alerts: [],
};

afterEach(() => vi.unstubAllGlobals());

test("envia o cenário e mostra o resultado por processo", async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(result), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenariosPage dimensions={dims} />);

  await userEvent.type(screen.getByLabelText("Volume de Recebimento (%)"), "20");
  await userEvent.selectOptions(screen.getByLabelText("Ratear compartilhados por"), "order_picked");
  await userEvent.click(screen.getByRole("button", { name: "Simular" }));

  const kpis = await screen.findByLabelText("Resultado do cenário");
  expect(within(kpis).getByText(/\+R\$\s10\.000,00/)).toBeInTheDocument();
  expect(within(kpis).getByText("+6,25%")).toBeInTheDocument();
  expect(screen.getByText("(+20%)")).toBeInTheDocument();

  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe("/api/v1/scenarios/simulate");
  const body = JSON.parse(String(init.body));
  expect(body.volume_changes).toEqual([{ process_code: "REC", percent: "20" }]);
  expect(body.variable_cost_share).toBe("1");
  expect(body.allocation_driver_code).toBe("order_picked");
});

test("erro da API aparece sem apagar o formulário", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            error: { code: "INVALID_SCENARIO", message: "O cenário tem campos inválidos.", details: [] },
          }),
          { status: 422 },
        ),
    ),
  );
  render(<ScenariosPage dimensions={dims} />);
  await userEvent.click(screen.getByRole("button", { name: "Simular" }));
  expect(await screen.findByText(/O cenário tem campos inválidos/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Simular" })).toBeEnabled();
});
