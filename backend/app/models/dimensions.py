from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Unit(Base):
    """Unidade operacional (CD, loja etc.)."""

    __tablename__ = "units"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    unit_type: Mapped[str] = mapped_column(String(40), server_default="distribution_center")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Driver(Base):
    """Direcionador de custo; sempre com unidade de medida explícita."""

    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    unit_of_measure: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Process(Base):
    """Processo logístico (recebimento, armazenagem, picking...)."""

    __tablename__ = "processes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    default_driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class CostCenter(Base):
    __tablename__ = "cost_centers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Account(Base):
    """Conta contábil."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    cost_nature: Mapped[str | None] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
