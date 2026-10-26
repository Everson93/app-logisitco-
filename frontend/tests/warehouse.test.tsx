import { render, screen, within } from "@testing-library/react";

import { WarehousePage } from "../src/features/warehouse/WarehousePage";
import type { Warehouse, WarehouseIndicators } from "../src/types/api";

const pick: WarehouseIndicators = {
  total_cost: "50000.00",
  direct_cost: "50000.00",
  allocated_cost: "0.00",
  volume: "5000.0000",
  driver_uom: "order",
  unit_cost: "10.0000",
  direct_unit_cost: "10.0000",
  allocated_unit_cost: "0.0000",
  productive_hours: "1000.0000",
  productivity_per_hour: "5.00",
  cost_per_hour: "50.00",
  lines: "15000.0000",
  lines_per_hour: "15.00",
  lines_per_order: "3.00",
};

const arm: WarehouseIndicators = {
  ...pick,
  total_cost: "9000.00",
  direct_cost: "9000.00",
  volume: "3000.0000",
  driver_uom: "position_day",
  unit_cost: "3.0000",
  direct_unit_cost: "3.0000",
  productive_hours: null,
  productivity_per_hour: null,
  cost_per_hour: null,
  lines: null,
  lines_per_hour: null,
  lines_per_order: null,
};

const body: Warehouse = {
  period: { from: "2026-08-01", to: "2026-09-30" },
  currency: "BRL",
  items: [
    {
      process_id: 2,
      process_code: "ARM",
      process_name: "Armazenagem",
      ...arm,
      months: [
        { period: "2026-08-01", calculated: false },
        { period: "2026-09-01", calculated: true, ...arm },
      ],
    },
    {
      process_id: 3,
      process_code: "PICK",
      process_name: "Separação / picking",
      ...pick,
      months: [
        { period: "2026-08-01", calculated: false },
        { period: "2026-09-01", calculated: true, ...pick },
      ],
    },
  ],
  alerts: [
    {
      code: "NO_PRODUCTIVE_HOURS",
      severity: "info",
      message: "Sem horas produtivas para ARM: produtividade e custo por hora ficam N/D.",
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

test("mostra produtividade do picking e N/D onde não há horas", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })),
  );
  render(<WarehousePage dimensions={null} />);

  const kpis = await screen.findByLabelText("Indicadores de picking");
  expect(within(kpis).getByText(/R\$\s10,00 \/ pedido/)).toBeInTheDocument();
  expect(within(kpis).getByText("5 / h")).toBeInTheDocument();
  expect(within(kpis).getByText("15 / h")).toBeInTheDocument();
  expect(within(kpis).getByText("3")).toBeInTheDocument();
  expect(within(kpis).getByText(/R\$\s50,00/)).toBeInTheDocument();

  const arm = screen.getByRole("row", { name: /ARM · Armazenagem/ });
  expect(within(arm).getAllByText("N/D").length).toBeGreaterThanOrEqual(3);
  expect(screen.getByText(/Sem horas produtivas para ARM/)).toBeInTheDocument();
  expect(screen.getByText("5 pedidos / h")).toBeInTheDocument();
});
