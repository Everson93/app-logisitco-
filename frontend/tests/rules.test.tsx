import { fireEvent, render, screen, within } from "@testing-library/react";

import { RulesPage } from "../src/features/settings/RulesPage";
import type { AllocationRule, Dimensions } from "../src/types/api";

const dimensions: Dimensions = {
  units: [{ id: 1, code: "CD-DEMO-01", name: "CD Demo", unit_type: "distribution_center" }],
  processes: [
    { id: 10, code: "REC", name: "Recebimento", default_driver_id: 5 },
    { id: 12, code: "ADM", name: "Administração do CD", default_driver_id: null },
  ],
  drivers: [{ id: 9, code: "productive_hour", name: "Hora produtiva", unit_of_measure: "hour" }],
  accounts: [],
  cost_centers: [],
};

const cascadeRule: AllocationRule = {
  id: 2,
  name: "ADM por horas",
  driver_code: "productive_hour",
  valid_from: "2026-01-01",
  valid_to: null,
  scope: { source_process_codes: ["ADM"] },
  priority: 100,
  rounding: "largest_remainder",
  active: true,
  conflicts_with: [],
};

afterEach(() => vi.unstubAllGlobals());

test("cria regra de cascata com o processo de apoio no escopo", async () => {
  const posts: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posts.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify(cascadeRule), { status: 201 });
      }
      return new Response(JSON.stringify([cascadeRule]), { status: 200 });
    }),
  );
  render(<RulesPage dimensions={dimensions} />);

  expect(await screen.findByText("Cascata: repassa o custo de: ADM")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Tipo"), { target: { value: "cascade" } });
  fireEvent.change(screen.getByLabelText("Processo de apoio"), { target: { value: "ADM" } });
  fireEvent.change(screen.getByLabelText("Nome"), { target: { value: "ADM por horas" } });
  fireEvent.change(screen.getByLabelText("Direcionador"), {
    target: { value: "productive_hour" },
  });
  // O processo de apoio não aparece como destino.
  const targets = screen.getByLabelText("Ratear para o processo");
  expect(within(targets).queryByText("Administração do CD")).toBeNull();

  fireEvent.click(screen.getByRole("button", { name: "Criar regra" }));
  await vi.waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toMatchObject({
    driver_code: "productive_hour",
    scope: { source_process_codes: ["ADM"] },
  });
});
