from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from app.database import get_db
from app.dependencies import get_user_headers
from app.schemas import StandardResponse, OrderResponse, OrderCreate, OrderStatusUpdate
from app.services import order_service
from app.events.publisher import publish_event
from app.models.models import OrderStatusEnum
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
    
    # Publish event (best-effort — order is already committed to DB)
    try:
        items = [{"item_id": str(i.menu_item_id), "quantity": i.quantity} for i in order.items]
        await publish_event("order.placed", {
            "order_id": str(order.id),
            "user_id": user_id,
            "restaurant_id": str(order.restaurant_id),
            "items": items,
            "total": float(order.total_amount)
        })
    except Exception as e:
        print(f"[warn] publish_event order.placed failed (non-fatal): {e}")
    
    # Call payment service to create payment record (and Razorpay order if configured)
    payment_info: dict = {}
    try:
        async with httpx.AsyncClient() as client:
            payment_payload = {
                "order_id": str(order.id),
                "amount": float(order.total_amount),
                "method": payload.payment_method,
                "user_email": headers.get("email", ""),
                "user_name": headers.get("name", "User"),
                "restaurant_name": payload.restaurant_name_snapshot,
                "delivery_floor": payload.delivery_floor,
                "delivery_wing": payload.delivery_wing,
                "estimated_minutes": 20,
                "items": [
                    {"name": i.item_name_snapshot, "qty": i.quantity, "price": float(i.item_price_snapshot)}
                    for i in order.items
                ],
            }
            resp = await client.post(
                f"{settings.payment_service_url}/payments",
                json=payment_payload,
                headers={"X-User-ID": user_id, "Authorization": headers.get("raw_auth", "")},
                timeout=10.0,
            )
            if resp.status_code == 200:
                resp_json = resp.json()
                pd = resp_json.get("data") or {}
                payment_info = {
                    "payment_id": pd.get("id"),
                    "razorpay_order_id": pd.get("razorpay_order_id"),
                    "razorpay_key_id": pd.get("razorpay_key_id"),
                }
    except Exception as e:
        print(f"[warn] Failed to reach payment service (non-fatal): {e}")

    order_data = OrderResponse.model_validate(order).model_dump(mode="json")
    order_data["payment_info"] = payment_info
    return format_response(order_data, "Order placed")

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
        
    try:
        if payload.status == OrderStatusEnum.CONFIRMED:
            await publish_event("order.confirmed", {"order_id": id, "user_id": str(order.user_id), "restaurant_id": str(order.restaurant_id)})
        elif payload.status == OrderStatusEnum.DELIVERED:
            await publish_event("order.delivered", {"order_id": id, "user_id": str(order.user_id)})
    except Exception as e:
        print(f"[warn] publish_event status update failed (non-fatal): {e}")
        
    return format_response(OrderResponse.model_validate(order).model_dump(mode="json"))

@router.post("/{id}/cancel", response_model=StandardResponse)
async def cancel_order(id: str, db: AsyncSession = Depends(get_db), headers: dict = Depends(get_user_headers)):
    user_id = headers.get("user_id")
    order = await order_service.update_order_status(db, id, OrderStatusEnum.CANCELLED)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    try:
        await publish_event("order.cancelled", {"order_id": id, "user_id": user_id, "reason": "User requested cancel"})
    except Exception as e:
        print(f"[warn] publish_event order.cancelled failed (non-fatal): {e}")
    return format_response(OrderResponse.model_validate(order).model_dump(mode="json"), "Order cancelled")

@router.get("/{id}/track", response_model=StandardResponse)
async def track_order(id: str, db: AsyncSession = Depends(get_db)):
    order = await order_service.get_order(db, id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return format_response(OrderResponse.model_validate(order).model_dump(mode="json"))
