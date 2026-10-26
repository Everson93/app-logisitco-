// Formatação pt-BR. Dado desconhecido vira "N/D", nunca zero (seção 11, padrões de UX).

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

export const ND = "N/D";

type Numeric = string | number | null | undefined;

export function toNumber(value: Numeric): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export function money(value: Numeric): string {
  const n = toNumber(value);
  return n === null ? ND : brl.format(n);
}

/** Valor com sinal explícito: o desvio não depende só de cor (seção 5.5). */
export function signedMoney(value: Numeric): string {
  const n = toNumber(value);
  if (n === null) return ND;
  return n > 0 ? `+${brl.format(n)}` : brl.format(n);
}

export function signedPercent(value: Numeric): string {
  const n = toNumber(value);
  if (n === null) return ND;
  const text = `${number.format(Math.abs(n))}%`;
  return n > 0 ? `+${text}` : n < 0 ? `−${text}` : text;
}

export function quantity(value: Numeric, uom?: string | null): string {
  const n = toNumber(value);
  if (n === null) return ND;
  return uom ? `${number.format(n)} ${uomLabel(uom)}` : number.format(n);
}

export function unitCost(value: Numeric, uom?: string | null): string {
  const n = toNumber(value);
  if (n === null) return ND;
  const formatted = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(n);
  return uom ? `${formatted} / ${uomLabel(uom, true)}` : formatted;
}

const UOM: Record<string, [string, string]> = {
  pallet: ["paletes", "palete"],
  position_day: ["posições-dia", "posição-dia"],
  order: ["pedidos", "pedido"],
  trip: ["viagens", "viagem"],
};

export function uomLabel(uom: string, singular = false): string {
  const label = UOM[uom];
  return label ? label[singular ? 1 : 0] : uom;
}

export function varianceLabel(value: Numeric): string {
  const n = toNumber(value);
  if (n === null) return "sem orçamento";
  if (n > 0) return "acima do orçamento";
  if (n < 0) return "abaixo do orçamento";
  return "no orçamento";
}

export function monthLabel(iso: string): string {
  const [year, month] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("pt-BR", { month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(year, month - 1, 1)))
    .replace(".", "");
}

/** "2026-09" -> primeiro e último dia do mês. */
export function monthRange(fromMonth: string, toMonth: string): { from: string; to: string } {
  const [ty, tm] = toMonth.split("-").map(Number);
  const lastDay = new Date(Date.UTC(ty, tm, 0)).getUTCDate();
  return { from: `${fromMonth}-01`, to: `${toMonth}-${String(lastDay).padStart(2, "0")}` };
}
