import { fireEvent, render, screen, within } from "@testing-library/react";

import { DimensionsPage } from "../src/features/settings/DimensionsPage";
import type { DimensionItem } from "../src/types/api";

const units: DimensionItem[] = [
  { id: 1, code: "CD-DEMO-01", name: "CD Demo", active: true, unit_type: "distribution_center" },
  { id: 2, code: "LOJA-DEMO-02", name: "Loja Sul", active: false, unit_type: "store" },
];
const drivers: DimensionItem[] = [
  { id: 5, code: "pallet_received", name: "Palete recebido", active: true, unit_of_measure: "pallet" },
];

function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

afterEach(() => vi.unstubAllGlobals());

test("lista, cria e mostra o motivo quando o direcionador está em uso", async () => {
  const calls: { url: string; method: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (method === "POST") return reply({ ...units[0], id: 3, code: "LOJA-DEMO-03" }, 201);
      if (method === "PATCH")
        return reply(
          {
            error: {
              code: "DIMENSION_IN_USE",
              message: "O direcionador está em uso.",
              details: [{ field: "process", value: "REC", code: "DEFAULT_DRIVER" }],
            },
          },
          409,
        );
      return reply(url.endsWith("/drivers") ? drivers : units);
    }),
  );
  const onChanged = vi.fn();
  render(<DimensionsPage onChanged={onChanged} />);

  const inactive = await screen.findByRole("row", { name: /LOJA-DEMO-02/ });
  expect(within(inactive).getByText("Loja")).toBeInTheDocument();
  expect(within(inactive).getByRole("button", { name: /Inativo · ativar/ })).toBeInTheDocument();

  const form = screen.getByRole("form", { name: "Formulário de cadastro" });
  fireEvent.change(within(form).getByLabelText("Código"), { target: { value: "LOJA-DEMO-03" } });
  fireEvent.change(within(form).getByLabelText("Nome"), { target: { value: "Loja Leste" } });
  fireEvent.change(within(form).getByLabelText("Tipo"), { target: { value: "store" } });
  fireEvent.click(within(form).getByRole("button", { name: "Criar" }));

  await vi.waitFor(() => expect(onChanged).toHaveBeenCalled());
  const post = calls.find((c) => c.method === "POST");
  expect(post?.url).toBe("/api/v1/dimensions/units");
  expect(post?.body).toEqual({ code: "LOJA-DEMO-03", name: "Loja Leste", unit_type: "store" });

  fireEvent.click(screen.getByRole("button", { name: "Direcionadores" }));
  const row = await screen.findByRole("row", { name: /pallet_received/ });
  fireEvent.click(within(row).getByRole("button", { name: /Ativo · desativar/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("process · REC · DEFAULT_DRIVER");
});
