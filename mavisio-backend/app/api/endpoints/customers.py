import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.models import Customer, User
from app.db.schemas import CustomerCreate, CustomerOut
from app.db.session import get_db

router = APIRouter()


async def _owned(db: AsyncSession, customer_id: uuid.UUID, user: User) -> Customer:
    customer = await db.get(Customer, customer_id)
    if not customer or customer.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("", response_model=CustomerOut, status_code=201)
async def create(
    body: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer = Customer(owner_id=user.id, **body.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("", response_model=list[CustomerOut])
async def list_all(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    result = await db.scalars(
        select(Customer)
        .where(Customer.owner_id == user.id)
        .order_by(Customer.created_at.desc())
    )
    return list(result)


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_one(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _owned(db, customer_id, user)


@router.delete("/{customer_id}", status_code=204)
async def delete(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.delete(await _owned(db, customer_id, user))
    await db.commit()
    return Response(status_code=204)
