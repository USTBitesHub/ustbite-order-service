from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from app.database import get_db
from app.dependencies import get_user_headers
from app.schemas import StandardResponse, OrderResponse, OrderCreate, OrderStatusUpdate
from app.services import order_service
from app.events.publisher import publish_event
from app.models import OrderStatusEnum
from app.config import settings

router = APIRouter(prefix="/orders", tags=["Orders"])

def format_response(data, message="Success"):
    return {"data": data, "message": message, "status": "success"}

@router.post("", response_model=StandardResponse)
async def place_order(payload: OrderCreate, db: AsyncSession = Depends(get_db), headers: dict = Depends(get_user_headers), x_trace_id: str = Header(None)):
    user_id = headers.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")
    
    order = await order_service.create_order(db, user_id, payload)
    
    # Publish event
    items = [{"item_id": str(i.menu_item_id), "quantity": i.quantity} for i in order.items]
    await publish_event("order.placed", {
        "order_id": str(order.id),
        "user_id": user_id,
        "restaurant_id": str(order.restaurant_id),
        "items": items,
        "total": float(order.total_amount)
    })
    
    # Synchronous call to payment service
    try:
        async with httpx.AsyncClient() as client:
            payment_payload = {
                "order_id": str(order.id),
                "amount": float(order.total_amount),
                "method": "UPI" # Defaulting for simplicity
            }
            resp = await client.post(
                "http://ustbite-payment-service:8004/payments",
                json=payment_payload,
                headers={"X-User-ID": user_id, "X-Trace-ID": x_trace_id or ""}
            )
            # We don't wait for it to be SUCCESS, we just initiate it.
            # Real status updates will come through rabbitmq events.
    except Exception as e:
        print(f"Failed to reach payment service: {e}")
        
    return format_response(OrderResponse.model_validate(order).model_dump(mode="json"), "Order placed")

@router.get("/me", response_model=StandardResponse)
async def get_my_orders(page: int = Query(1, ge=1), limit: int = Query(20, le=100), db: AsyncSession = Depends(get_db), headers: dict = Depends(get_user_headers)):
    user_id = headers.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")
    skip = (page - 1) * limit
    orders = await order_service.get_user_orders(db, user_id, skip=skip, limit=limit)
    data = [OrderResponse.model_validate(o).model_dump(mode="json") for o in orders]
    return format_response(data)

@router.get("/{id}", response_model=StandardResponse)
async def get_order(id: str, db: AsyncSession = Depends(get_db)):
    order = await order_service.get_order(db, id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return format_response(OrderResponse.model_validate(order).model_dump(mode="json"))

@router.put("/{id}/status", response_model=StandardResponse)
async def update_status(id: str, payload: OrderStatusUpdate, db: AsyncSession = Depends(get_db)):
    order = await order_service.update_order_status(db, id, payload.status)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if payload.status == OrderStatusEnum.CONFIRMED:
        await publish_event("order.confirmed", {"order_id": id, "user_id": str(order.user_id), "restaurant_id": str(order.restaurant_id)})
    elif payload.status == OrderStatusEnum.DELIVERED:
        await publish_event("order.delivered", {"order_id": id, "user_id": str(order.user_id)})
        
    return format_response(OrderResponse.model_validate(order).model_dump(mode="json"))

@router.post("/{id}/cancel", response_model=StandardResponse)
async def cancel_order(id: str, db: AsyncSession = Depends(get_db), headers: dict = Depends(get_user_headers)):
    user_id = headers.get("user_id")
    order = await order_service.update_order_status(db, id, OrderStatusEnum.CANCELLED)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    await publish_event("order.cancelled", {"order_id": id, "user_id": user_id, "reason": "User requested cancel"})
    return format_response(OrderResponse.model_validate(order).model_dump(mode="json"), "Order cancelled")

@router.get("/{id}/track", response_model=StandardResponse)
async def track_order(id: str, db: AsyncSession = Depends(get_db)):
    order = await order_service.get_order(db, id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    # Simplified tracking
    return format_response({"status": order.status, "updated_at": order.updated_at.isoformat() if order.updated_at else None})
