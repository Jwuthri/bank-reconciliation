from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from humanize import intcomma, ordinal
from pydantic import BaseModel

from .db.database import db
from .db.init_db import init_db
from .reconciliation import ReconciliationEngine
from .reconciliation.engine import LiveReconciliationEngine

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

engine: ReconciliationEngine = LiveReconciliationEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect(reuse_if_open=True)
    init_db()
    engine.run_matching()
    yield
    if not db.is_closed():
        db.close()


app = FastAPI(title="Lassie Dashboard", lifespan=lifespan)


class ManualReconcileRequest(BaseModel):
    eob_id: int
    transaction_id: int


class DismissEOBRequest(BaseModel):
    eob_id: int


class DismissTransactionRequest(BaseModel):
    transaction_id: int


class RunPipelineRequest(BaseModel):
    use_llm: bool = True
    overwrite: bool = False


def format_date(dt: datetime) -> str:
    return f"{dt.strftime('%B')} {ordinal(dt.day)}"


def format_currency(cents: int | None) -> str:
    if cents is None:
        return "N/A"
    return f"${intcomma(cents / 100)}"


templates.env.filters["format_date"] = format_date
templates.env.filters["format_currency"] = format_currency
templates.env.filters["intcomma"] = lambda x: intcomma(x) if x is not None else "0"


@app.post("/api/reconcile")
def api_reconcile(body: ManualReconcileRequest) -> JSONResponse:
    """Create a manual match between an EOB and a bank transaction."""
    try:
        match_id = engine.manual_reconcile(
            eob_id=body.eob_id, transaction_id=body.transaction_id
        )
        return JSONResponse({"ok": True, "match_id": match_id})
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/reconcile/dismiss")
def api_dismiss_eob(body: DismissEOBRequest) -> JSONResponse:
    """Dismiss an unmatched EOB (no transaction expected)."""
    try:
        match_id = engine.dismiss_item(eob_id=body.eob_id)
        return JSONResponse({"ok": True, "match_id": match_id})
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/match-detail")
def api_match_detail(
    eob_id: int | None = Query(None),
    transaction_id: int | None = Query(None),
) -> JSONResponse:
    """Return EOB and/or bank_transaction as JSON for a given match or single item."""
    from .db.models import (
        BankTransaction,
        EOB,
        Payer,
        ReconciliationMatch,
    )

    result: dict = {"eob": None, "bank_transaction": None, "match": None}

    if eob_id is not None:
        eob = EOB.get_or_none(EOB.id == eob_id)
        if eob:
            result["eob"] = {
                "id": eob.id,
                "payment_number": eob.payment_number,
                "payer_id": eob.payer_id,
                "payer_name": eob.payer.name,
                "payment_amount": eob.payment_amount,
                "adjusted_amount": eob.adjusted_amount,
                "payment_type": eob.payment_type,
                "payment_date": eob.payment_date.isoformat() if eob.payment_date else None,
            }
            match = ReconciliationMatch.get_or_none(ReconciliationMatch.eob == eob_id)
            if match:
                result["match"] = {
                    "id": match.id,
                    "confidence": match.confidence,
                    "match_method": match.match_method,
                    "matched_at": match.matched_at.isoformat() if match.matched_at else None,
                }
                if match.bank_transaction_id:
                    bt = match.bank_transaction
                    result["bank_transaction"] = {
                        "id": bt.id,
                        "amount": bt.amount,
                        "note": bt.note,
                        "received_at": bt.received_at.isoformat() if bt.received_at else None,
                    }

    if transaction_id is not None and result["bank_transaction"] is None:
        bt = BankTransaction.get_or_none(BankTransaction.id == transaction_id)
        if bt:
            result["bank_transaction"] = {
                "id": bt.id,
                "amount": bt.amount,
                "note": bt.note,
                "received_at": bt.received_at.isoformat() if bt.received_at else None,
            }
            match = ReconciliationMatch.get_or_none(
                ReconciliationMatch.bank_transaction == transaction_id
            )
            if match:
                result["match"] = {
                    "id": match.id,
                    "confidence": match.confidence,
                    "match_method": match.match_method,
                    "matched_at": match.matched_at.isoformat() if match.matched_at else None,
                }
                if result["eob"] is None:
                    eob = match.eob
                    result["eob"] = {
                        "id": eob.id,
                        "payment_number": eob.payment_number,
                        "payer_id": eob.payer_id,
                        "payer_name": eob.payer.name,
                        "payment_amount": eob.payment_amount,
                        "adjusted_amount": eob.adjusted_amount,
                        "payment_type": eob.payment_type,
                        "payment_date": eob.payment_date.isoformat() if eob.payment_date else None,
                    }

    return JSONResponse(result)


@app.post("/api/run-pipeline")
def api_run_pipeline(
    body: RunPipelineRequest = Body(default=RunPipelineRequest()),
) -> JSONResponse:
    """Run the full pipeline: classify (is insurance) then reconcile on all data."""
    use_llm = body.use_llm
    overwrite = body.overwrite
    try:
        stats = engine.run_matching(use_llm=use_llm, overwrite=overwrite)
        return JSONResponse(
            {
                "ok": True,
                "classified": stats.get("classified", 0),
                "matched": stats.get("matched", 0),
                "skipped_existing": stats.get("skipped_existing", 0),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reconcile/dismiss-transaction")
def api_dismiss_transaction(body: DismissTransactionRequest) -> JSONResponse:
    """Dismiss an unmatched transaction (not reconcilable)."""
    try:
        engine.dismiss_item(transaction_id=body.transaction_id)
        return JSONResponse({"ok": True})
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    section: str = Query(
        "inbox", pattern="^(inbox|payments|overview)$"
    ),
    tab: str = Query("missing_eobs", pattern="^(missing_eobs|missing_txn)$"),
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("date", pattern="^(date|payer|payment_number|amount|method)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    if section == "overview":
        stats = engine.get_stats()
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "section": section,
                "tab": tab,
                "view": "overview",
                "stats": stats,
                "page": page,
                "page_size": page_size,
                "sort_by": "date",
                "sort_order": "desc",
            },
        )

    if section == "payments":
        result = engine.get_dashboard_payments(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        view = "payments"
    elif tab == "missing_txn":
        result = engine.get_missing_bank_transactions(page=page, page_size=page_size)
        view = "missing_txn"
    else:
        result = engine.get_missing_payment_eobs(page=page, page_size=page_size)
        view = "missing_eobs"

    start_idx = result.page * result.page_size + 1
    end_idx = min(start_idx + len(result.items) - 1, result.total_count)

    if section != "payments":
        sort_by = "date"
        sort_order = "desc"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "section": section,
            "tab": tab,
            "view": view,
            "result": result,
            "page": page,
            "page_size": page_size,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )
