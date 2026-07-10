from fastapi import APIRouter

from core.routers import trading_proposals, trading_risk, trading_trader

router = APIRouter()
router.include_router(trading_proposals.router)
router.include_router(trading_risk.router)
router.include_router(trading_trader.router)
