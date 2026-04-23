from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from .models import Order, OrderItem, OrderStatusEnum
from .schemas import OrderCreate, OrderStatusUpdate

async def get_order(db: AsyncSession, order_id: str):
    result = await db.execute(select(Order).options(selectinload(Order.items)).filter(Order.id == order_id))
    return result.scalars().first()

async def get_user_orders(db: AsyncSession, user_id: str, skip: int = 0, limit: int = 20):
    result = await db.execute(
        select(Order).options(selectinload(Order.items))
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .offset(skip).limit(limit)
    )
    return result.scalars().all()

async def create_order(db: AsyncSession, user_id: str, payload: OrderCreate):
    items_data = payload.items
    order_data = payload.model_dump(exclude={"items"})
    db_order = Order(**order_data, user_id=user_id)
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)
    
    for item in items_data:
        db_item = OrderItem(**item.model_dump(), order_id=db_order.id)
        db.add(db_item)
    
    await db.commit()
    return await get_order(db, str(db_order.id))

async def update_order_status(db: AsyncSession, order_id: str, status: OrderStatusEnum):
    db_order = await get_order(db, order_id)
    if not db_order:
        return None
    db_order.status = status
    await db.commit()
    await db.refresh(db_order)
    return db_order
