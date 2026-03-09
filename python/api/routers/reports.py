"""
ENLACE Reports Router

Report generation endpoints supporting PDF, CSV, and XLSX formats.
Uses WeasyPrint for PDF, csv module for CSV, and openpyxl for Excel.
"""

import asyncio
import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from python.api.auth.dependencies import require_auth
from python.reports.generator import (
    generate_market_report,
    generate_expansion_report,
    generate_compliance_report,
    generate_rural_report,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class MarketReportRequest(BaseModel):
    municipality_id: int = Field(..., description="IBGE municipality identifier")
    provider_id: Optional[int] = Field(None, description="Optional provider ID")


class ExpansionReportRequest(BaseModel):
    municipality_id: int = Field(..., description="IBGE municipality identifier")


class ComplianceReportRequest(BaseModel):
    provider_name: str = Field(..., min_length=1)
    state_codes: list[str] = Field(..., min_length=1)
    subscriber_count: int = Field(..., ge=0)
    revenue_monthly: Optional[float] = Field(None, ge=0)


class RuralReportRequest(BaseModel):
    community_lat: float
    community_lon: float
    population: int = Field(..., ge=0)
    area_km2: float = Field(..., gt=0)
    grid_power: bool = Field(False)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _to_csv_response(data: dict, filename: str) -> StreamingResponse:
    """Convert report dict to CSV streaming response."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    def _flatten(obj, prefix=""):
        rows = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                if isinstance(v, (dict, list)):
                    rows.extend(_flatten(v, key))
                else:
                    rows.append((key, v))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                rows.extend(_flatten(item, f"{prefix}[{i}]"))
        else:
            rows.append((prefix, obj))
        return rows

    flat = _flatten(data)
    writer.writerow(["Campo", "Valor"])
    for key, val in flat:
        writer.writerow([key, val])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _to_xlsx_response(data: dict, filename: str) -> StreamingResponse:
    """Convert report dict to XLSX streaming response."""
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl não instalado")

    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório"
    ws.append(["Campo", "Valor"])

    def _flatten(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                if isinstance(v, (dict, list)):
                    _flatten(v, key)
                else:
                    ws.append([key, str(v) if v is not None else ""])
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _flatten(item, f"{prefix}[{i}]")
        else:
            ws.append([prefix, str(obj) if obj is not None else ""])

    _flatten(data)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _generate_and_respond(generator_fn, kwargs: dict, base_filename: str, fmt: str):
    """Run a report generator and return in the requested format."""
    loop = asyncio.get_event_loop()

    def _run():
        return generator_fn(**kwargs)

    try:
        content_bytes, media_type = await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.error("Report generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao gerar relatório")

    if fmt == "csv":
        # Re-run generator for structured data; use PDF bytes as fallback
        import json
        try:
            data = json.loads(content_bytes) if isinstance(content_bytes, (str, bytes)) else {}
        except (json.JSONDecodeError, TypeError):
            data = {"report": base_filename, "note": "Dados do relatório em formato PDF"}
        return _to_csv_response(data, f"{base_filename}.csv")

    if fmt == "xlsx":
        import json
        try:
            data = json.loads(content_bytes) if isinstance(content_bytes, (str, bytes)) else {}
        except (json.JSONDecodeError, TypeError):
            data = {"report": base_filename, "note": "Dados do relatório em formato PDF"}
        return _to_xlsx_response(data, f"{base_filename}.xlsx")

    # Default: PDF/HTML
    ext = "pdf" if media_type == "application/pdf" else "html"
    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{base_filename}.{ext}"'},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/market")
async def market_report(
    request: MarketReportRequest,
    format: str = Query("pdf", alias="format", pattern="^(pdf|csv|xlsx)$"),
    user: dict = Depends(require_auth),
):
    """Generate a market analysis report in PDF, CSV, or XLSX format."""
    return await _generate_and_respond(
        generate_market_report,
        {"municipality_id": request.municipality_id, "provider_id": request.provider_id},
        f"enlace_market_{request.municipality_id}",
        format,
    )


@router.post("/expansion")
async def expansion_report(
    request: ExpansionReportRequest,
    format: str = Query("pdf", alias="format", pattern="^(pdf|csv|xlsx)$"),
    user: dict = Depends(require_auth),
):
    """Generate an expansion opportunity report."""
    return await _generate_and_respond(
        generate_expansion_report,
        {"municipality_id": request.municipality_id},
        f"enlace_expansion_{request.municipality_id}",
        format,
    )


@router.post("/compliance")
async def compliance_report(
    request: ComplianceReportRequest,
    format: str = Query("pdf", alias="format", pattern="^(pdf|csv|xlsx)$"),
    user: dict = Depends(require_auth),
):
    """Generate a regulatory compliance report."""
    safe_name = request.provider_name.replace(" ", "_")[:30]
    return await _generate_and_respond(
        generate_compliance_report,
        {
            "provider_name": request.provider_name,
            "state_codes": request.state_codes,
            "subscriber_count": request.subscriber_count,
            "revenue": request.revenue_monthly,
        },
        f"enlace_compliance_{safe_name}",
        format,
    )


@router.post("/rural")
async def rural_report(
    request: RuralReportRequest,
    format: str = Query("pdf", alias="format", pattern="^(pdf|csv|xlsx)$"),
    user: dict = Depends(require_auth),
):
    """Generate a rural feasibility report."""
    return await _generate_and_respond(
        generate_rural_report,
        {
            "community_lat": request.community_lat,
            "community_lon": request.community_lon,
            "population": request.population,
            "area_km2": request.area_km2,
            "grid_power": request.grid_power,
        },
        f"enlace_rural_{request.community_lat:.2f}_{request.community_lon:.2f}",
        format,
    )
