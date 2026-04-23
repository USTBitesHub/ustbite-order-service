from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from .models import OrderStatusEnum

class StandardResponse(BaseModel):
    data: Optional[dict | list] = None
    message: str
    status: str

class OrderItemCreate(BaseModel):
    menu_item_id: UUID
    item_name_snapshot: str
    item_price_snapshot: Decimal
    quantity: int
    subtotal: Decimal

class OrderCreate(BaseModel):
    restaurant_id: UUID
    restaurant_name_snapshot: str
    total_amount: Decimal
    delivery_floor: Optional[str] = None
    delivery_wing: Optional[str] = None
    special_instructions: Optional[str] = None
    items: List[OrderItemCreate]

class OrderStatusUpdate(BaseModel):
    status: OrderStatusEnum

class OrderItemResponse(OrderItemCreate):
    id: UUID
    order_id: UUID
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    restaurant_id: UUID
    restaurant_name_snapshot: str
    status: OrderStatusEnum
    total_amount: Decimal
    delivery_floor: Optional[str]
    delivery_wing: Optional[str]
    special_instructions: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    items: List[OrderItemResponse]
    model_config = ConfigDict(from_attributes=True)
