from fastapi import APIRouter, HTTPException

from app import mock_data
from app.config import get_settings
from app.models import SavingsSummary

router = APIRouter(prefix="/savings", tags=["savings"])
settings = get_settings()


@router.get("", response_model=SavingsSummary)
async def savings_summary() -> SavingsSummary:
    if settings.mock_mode:
        return mock_data.SAVINGS
    # TODO(L2): aggregate claims from Mongo + finance.solana_vault.get_vault_balance()
    raise HTTPException(501, "Not implemented")
