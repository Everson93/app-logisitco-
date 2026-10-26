import { render, screen, within } from "@testing-library/react";

import { TransportPage } from "../src/features/transport/TransportPage";
import type { Transport, TransportIndicators } from "../src/types/api";

const indicators: TransportIndicators = {
  total_cost: "40000.00",
  direct_cost: "40000.00",
  allocated_cost: "0.00",
  own_fleet_cost: "10000.00",
  third_party_cost: "30000.00",
  other_direct_cost: "0.00",
  trips: "100.0000",
  km: "8000.0000",
  pallets: "2000.0000",
  capacity_pallets: "2500.0000",
  cost_per_trip: "400.0000",
  cost_per_km: "5.0000",
  cost_per_pallet: "20.0000",
  km_per_trip: "80.00",
  occupancy_percent: "80.00",
};

const body: Transport = {
  period: { from: "2026-08-01", to: "2026-09-30" },
  currency: "BRL",
  ...indicators,
  months: [
    { period: "2026-08-01", calculated: false },
    { period: "2026-09-01", calculated: true, ...indicators },
  ],
  alerts: [],
};

afterEach(() => vi.unstubAllGlobals());

test("mostra custo por viagem, km, palete, ocupação e a divisão da frota", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })),
  );
  render(<TransportPage dimensions={null} />);

  const kpis = await screen.findByLabelText("Indicadores de transporte");
  expect(within(kpis).getByText(/R\$\s400,00 \/ viagem/)).toBeInTheDocument();
  expect(within(kpis).getByText(/R\$\s5,00 \/ km/)).toBeInTheDocument();
  expect(within(kpis).getByText(/R\$\s20,00 \/ palete/)).toBeInTheDocument();
  expect(within(kpis).getByText("80%")).toBeInTheDocument();
  expect(screen.getByText("25%")).toBeInTheDocument();
  expect(screen.getByText("75%")).toBeInTheDocument();
  expect(screen.getByText("sem cálculo executado")).toBeInTheDocument();
});
