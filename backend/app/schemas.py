from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class FarmerRegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = ""
    village: str = ""


class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    full_name: str
    role: str = Field(pattern="^(admin|operator)$")
    centre_id: int | None = None


class FarmerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = ""
    village: str = ""


class BatchIn(BaseModel):
    farmer_id: int
    variety: str = "Red Onion"
    quantity_kg: float = Field(gt=0, le=1_000_000)
    commodity: str = "Onion"
    centre_id: int | None = None


class StandardIn(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    config: dict
    activate: bool = True
