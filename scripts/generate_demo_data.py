"""Gera os CSVs fictícios de sample-data/ (seção 12 da especificação).

Determinístico: rodar de novo produz os mesmos arquivos. Todos os valores são
inventados e não representam nenhuma empresa.

Uso: python scripts/generate_demo_data.py
"""

import csv
from decimal import Decimal
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "sample-data"

MONTHS = ["2026-07", "2026-08", "2026-09"]
MONTH_END = {"2026-07": "31", "2026-08": "31", "2026-09": "30"}

# (unidade, processo) -> (conta, descrição, custo base, direcionador, quantidade base, UM)
OPERATIONS = {
    ("CD-DEMO-01", "REC"): (
        "6101",
        "Mao de obra recebimento",
        24000,
        "pallet_received",
        15000,
        "pallet",
    ),
    ("CD-DEMO-01", "ARM"): (
        "6102",
        "Custo de armazenagem",
        45000,
        "position_day",
        30000,
        "position_day",
    ),
    ("CD-DEMO-01", "PICK"): ("6103", "Custo de picking", 54000, "order_picked", 12000, "order"),
    ("CD-DEMO-01", "EXP"): ("6104", "Custo de expedicao", 27000, "pallet_shipped", 15000, "pallet"),
    ("CD-DEMO-01", "TRANS"): ("6105", "Frete distribuicao", 38000, "trip", 190, "trip"),
    ("LOJA-DEMO-01", "REC"): (
        "6101",
        "Mao de obra recebimento loja",
        6000,
        "pallet_received",
        2400,
        "pallet",
    ),
    ("LOJA-DEMO-01", "ARM"): (
        "6102",
        "Custo de estoque loja",
        4500,
        "position_day",
        3600,
        "position_day",
    ),
    ("LOJA-DEMO-02", "REC"): (
        "6101",
        "Mao de obra recebimento loja",
        5200,
        "pallet_received",
        2000,
        "pallet",
    ),
    ("LOJA-DEMO-02", "ARM"): (
        "6102",
        "Custo de estoque loja",
        3900,
        "position_day",
        3000,
        "position_day",
    ),
}

# Variação mensal fictícia de custo e volume, para que haja tendência e desvios.
COST_FACTOR = {"2026-07": Decimal("0.96"), "2026-08": Decimal("1.00"), "2026-09": Decimal("1.07")}
VOLUME_FACTOR = {"2026-07": Decimal("0.95"), "2026-08": Decimal("1.00"), "2026-09": Decimal("1.03")}

SHARED_COST = 30000  # custo compartilhado mensal do CD, a ser rateado por regra explícita

# Transporte (seção 5.7), em arquivos próprios para não alterar os três arquivos acima.
# Frete terceirizado continua em despesas_demo.csv (conta 6105); aqui entra a frota própria.
# mês -> (km total rodado, paletes transportados, capacidade nominal em paletes)
TRANSPORT_VOLUME = {
    "2026-07": (14760, 3960, 5040),
    "2026-08": (16150, 4370, 5320),
    "2026-09": (17248, 4704, 5488),
}
# mês -> (combustível, manutenção) da frota própria
FLEET_COST = {
    "2026-07": (Decimal("18450.00"), Decimal("4200.00")),
    "2026-08": (Decimal("20672.00"), Decimal("4350.00")),
    "2026-09": (Decimal("22422.40"), Decimal("6900.00")),
}
FLEET_BUDGET = (Decimal("20000.00"), Decimal("4500.00"))


def money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def write(name: str, header: list[str], rows: list[list[object]]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    expenses, activities, budgets = [], [], []
    exp_seq = act_seq = 0

    for month in MONTHS:
        last_day = f"{month}-{MONTH_END[month]}"
        for (unit, process), (account, desc, cost, driver, qty, uom) in OPERATIONS.items():
            exp_seq += 1
            amount = Decimal(cost) * COST_FACTOR[month]
            expenses.append(
                [
                    last_day,
                    unit,
                    process,
                    account,
                    desc,
                    money(amount),
                    "direct",
                    f"ERP-DEMO-{exp_seq:04d}",
                ]
            )
            act_seq += 1
            quantity = (Decimal(qty) * VOLUME_FACTOR[month]).quantize(Decimal(1))
            activities.append(
                [last_day, unit, process, driver, quantity, uom, f"ACT-DEMO-{act_seq:04d}"]
            )
            budgets.append([f"{month}-01", last_day, unit, process, account, money(Decimal(cost))])

        exp_seq += 1
        expenses.append(
            [
                last_day,
                "CD-DEMO-01",
                "",
                "6199",
                "Custo compartilhado demonstracao",
                money(Decimal(SHARED_COST)),
                "shared",
                f"ERP-DEMO-{exp_seq:04d}",
            ]
        )

    write(
        "despesas_demo.csv",
        [
            "competence_date",
            "unit_code",
            "process_code",
            "account_code",
            "description",
            "amount",
            "nature",
            "source_key",
        ],
        expenses,
    )
    write(
        "atividades_demo.csv",
        [
            "activity_date",
            "unit_code",
            "process_code",
            "driver_code",
            "quantity",
            "unit_of_measure",
            "source_key",
        ],
        activities,
    )
    write(
        "orcamento_demo.csv",
        ["period_start", "period_end", "unit_code", "process_code", "account_code", "amount"],
        budgets,
    )
    write_transport()


def write_transport() -> None:
    expenses, activities, budgets = [], [], []
    for n, month in enumerate(MONTHS, start=1):
        last_day = f"{month}-{MONTH_END[month]}"
        fuel, maintenance = FLEET_COST[month]
        for account, desc, amount, budget in (
            ("6106", "Combustivel frota propria", fuel, FLEET_BUDGET[0]),
            ("6107", "Manutencao frota propria", maintenance, FLEET_BUDGET[1]),
        ):
            expenses.append(
                [
                    last_day,
                    "CD-DEMO-01",
                    "TRANS",
                    account,
                    desc,
                    money(amount),
                    "direct",
                    f"FROTA-DEMO-{n:02d}-{account}",
                ]
            )
            budgets.append([f"{month}-01", last_day, "CD-DEMO-01", "TRANS", account, money(budget)])
        km, pallets, capacity = TRANSPORT_VOLUME[month]
        for driver, qty, uom in (
            ("km", km, "km"),
            ("pallet_transported", pallets, "pallet"),
            ("pallet_capacity", capacity, "pallet"),
        ):
            activities.append(
                [
                    last_day,
                    "CD-DEMO-01",
                    "TRANS",
                    driver,
                    qty,
                    uom,
                    f"TMS-DEMO-{n:02d}-{driver}",
                ]
            )

    write(
        "transporte_despesas_demo.csv",
        [
            "competence_date",
            "unit_code",
            "process_code",
            "account_code",
            "description",
            "amount",
            "nature",
            "source_key",
        ],
        expenses,
    )
    write(
        "transporte_atividades_demo.csv",
        [
            "activity_date",
            "unit_code",
            "process_code",
            "driver_code",
            "quantity",
            "unit_of_measure",
            "source_key",
        ],
        activities,
    )
    write(
        "transporte_orcamento_demo.csv",
        ["period_start", "period_end", "unit_code", "process_code", "account_code", "amount"],
        budgets,
    )


if __name__ == "__main__":
    main()
