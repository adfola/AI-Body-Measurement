import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_user
from app.db.models import Customer, MeasurementSession, User
from app.db.schemas import SessionOut
from app.db.session import get_db

router = APIRouter()


@router.get("/customers/{customer_id}/sessions", response_model=list[SessionOut])
async def customer_sessions(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer = await db.get(Customer, customer_id)
    if not customer or customer.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Customer not found")
    query = (
        select(MeasurementSession)
        .where(MeasurementSession.customer_id == customer_id)
        .options(selectinload(MeasurementSession.measurements))
        .order_by(MeasurementSession.created_at.desc())
    )
    return list(await db.scalars(query))


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def one_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(MeasurementSession)
        .where(MeasurementSession.id == session_id)
        .options(
            selectinload(MeasurementSession.measurements),
            selectinload(MeasurementSession.customer),
        )
    )
    session = await db.scalar(query)
    if not session or session.customer.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
