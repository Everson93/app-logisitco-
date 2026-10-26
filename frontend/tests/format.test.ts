import {
  ND,
  money,
  monthLabel,
  monthRange,
  quantity,
  signedMoney,
  signedPercent,
  unitCost,
  varianceLabel,
} from "../src/services/format";
import { defaultFilters } from "../src/features/dashboard/Filters";

// Intl usa espaço não separável entre "R$" e o número.
const clean = (s: string) => s.replace(/ /g, " ");

test("valores desconhecidos aparecem como N/D, nunca zero", () => {
  expect(money(null)).toBe(ND);
  expect(signedPercent(null)).toBe(ND);
  expect(unitCost(undefined, "pallet")).toBe(ND);
  expect(quantity("")).toBe(ND);
});

test("moeda e desvio com sinal explícito", () => {
  expect(clean(money("187500.00"))).toBe("R$ 187.500,00");
  expect(clean(signedMoney("22500.00"))).toBe("+R$ 22.500,00");
  expect(clean(signedMoney("-15000"))).toBe("-R$ 15.000,00");
  expect(signedPercent("13.64")).toBe("+13,64%");
  expect(signedPercent("-9.09")).toBe("−9,09%");
  expect(varianceLabel("1")).toBe("acima do orçamento");
  expect(varianceLabel("-1")).toBe("abaixo do orçamento");
  expect(varianceLabel(null)).toBe("sem orçamento");
});

test("unidade de medida junto do indicador", () => {
  expect(quantity("15000", "pallet")).toBe("15.000 paletes");
  expect(clean(unitCost("12.5", "pallet"))).toBe("R$ 12,50 / palete");
  expect(clean(unitCost("0.1234", "order"))).toBe("R$ 0,1234 / pedido");
});

test("intervalo de meses e rótulos", () => {
  expect(monthRange("2026-07", "2026-09")).toEqual({ from: "2026-07-01", to: "2026-09-30" });
  expect(monthRange("2028-02", "2028-02")).toEqual({ from: "2028-02-01", to: "2028-02-29" });
  expect(monthLabel("2026-09-01")).toBe("set de 2026");
});

test("filtro padrão: três últimos meses fechados", () => {
  expect(defaultFilters(new Date("2026-10-26T12:00:00Z"))).toEqual({
    fromMonth: "2026-07",
    toMonth: "2026-09",
    unitId: null,
    processId: null,
  });
  expect(defaultFilters(new Date("2027-01-15T12:00:00Z")).fromMonth).toBe("2026-10");
});
