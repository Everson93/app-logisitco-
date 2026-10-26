"""Cadastros (seção 11.4). O código é a chave usada na importação, por isso não muda depois de
criado; a unidade de medida do direcionador também não, para não invalidar volumes já
importados."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Code = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
Name = Annotated[str, Field(min_length=1, max_length=160)]
UnitType = Literal["distribution_center", "store"]
# Natureza da conta. Só `fleet_own` e `freight_third_party` mudam cálculos (transporte);
# as demais classificam a conta.
CostNature = Literal["personnel", "facility", "shared", "fleet_own", "freight_third_party"]


class UnitIn(BaseModel):
    code: Code
    name: Name
    unit_type: UnitType = "distribution_center"
    active: bool = True


class UnitUpdate(BaseModel):
    name: Name | None = None
    unit_type: UnitType | None = None
    active: bool | None = None


class DriverIn(BaseModel):
    code: Code
    name: Name
    unit_of_measure: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    active: bool = True


class DriverUpdate(BaseModel):
    name: Name | None = None
    active: bool | None = None


class ProcessIn(BaseModel):
    code: Code
    name: Name
    default_driver_code: str | None = None
    active: bool = True


class ProcessUpdate(BaseModel):
    name: Name | None = None
    default_driver_code: str | None = None
    active: bool | None = None


class AccountIn(BaseModel):
    code: Code
    name: Name
    cost_nature: CostNature | None = None
    active: bool = True


class AccountUpdate(BaseModel):
    name: Name | None = None
    cost_nature: CostNature | None = None
    active: bool | None = None


class CostCenterIn(BaseModel):
    code: Code
    name: Name
    unit_code: str | None = None
    active: bool = True


class CostCenterUpdate(BaseModel):
    name: Name | None = None
    unit_code: str | None = None
    active: bool | None = None
