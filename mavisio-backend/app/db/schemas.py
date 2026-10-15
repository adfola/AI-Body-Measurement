import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    height_cm: float = Field(ge=100, le=230)


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    height_cm: float | None
    created_at: datetime


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    value_cm: float

    @computed_field
    @property
    def value_inches(self) -> float:
        return round(self.value_cm / 2.54, 1)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    created_at: datetime
    measurements: list[MeasurementOut]
