from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from humanize import intcomma, ordinal

from .reconciliation import ReconciliationEngine
from .reconciliation.dummy_engine import DummyReconciliationEngine

app = FastAPI(title="Lassie Dashboard")

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

engine: ReconciliationEngine = DummyReconciliationEngine()


def format_date(dt: datetime) -> str:
    return f"{dt.strftime('%B')} {ordinal(dt.day)}"


def format_currency(cents: int | None) -> str:
    if cents is None:
        return "N/A"
    return f"${intcomma(cents / 100)}"


templates.env.filters["format_date"] = format_date
templates.env.filters["format_currency"] = format_currency


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    section: str = Query("inbox", pattern="^(inbox|payments)$"),
    tab: str = Query("missing_eobs", pattern="^(missing_eobs|missing_txn)$"),
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
):
    if section == "payments":
        result = engine.get_dashboard_payments(page=page, page_size=page_size)
        view = "payments"
    elif tab == "missing_txn":
        result = engine.get_missing_bank_transactions(page=page, page_size=page_size)
        view = "missing_txn"
    else:
        result = engine.get_missing_payment_eobs(page=page, page_size=page_size)
        view = "missing_eobs"

    start_idx = result.page * result.page_size + 1
    end_idx = min(start_idx + len(result.items) - 1, result.total_count)

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
        },
    )
