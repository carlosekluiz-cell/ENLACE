"""DCF (Discounted Cash Flow) valuation.

Projects 5-year cash flows and discounts to present value.

Parameters:
- Current revenue and growth trajectory
- EBITDA margin (typically 25-40% for Brazilian ISPs)
- CAPEX requirements (10-20% of revenue for maintenance)
- Working capital changes
- Terminal value using perpetuity growth model
- WACC for Brazilian telecom: 12-16% (includes country risk premium)
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Default 5-year revenue growth rates (declining over time)
DEFAULT_GROWTH_RATES: list[float] = [0.12, 0.10, 0.08, 0.06, 0.04]


@dataclass
class DCFValuation:
    """Result of DCF valuation."""

    projected_cashflows: list[dict]  # 5 years of FCF
    terminal_value_brl: float
    wacc_pct: float
    enterprise_value_brl: float
    equity_value_brl: float
    net_debt_brl: float
    sensitivity_table: dict  # WACC x growth rate matrix


def _project_cashflows(
    current_annual_revenue: float,
    growth_rates: list[float],
    ebitda_margin_pct: float,
    capex_pct_revenue: float,
    working_capital_pct_revenue: float = 3.0,
    tax_rate_pct: float = 34.0,
) -> list[dict]:
    """Project free cash flows for each year.

    FCF = EBITDA - Taxes on EBIT - CAPEX - Change in Working Capital

    For simplicity, we assume depreciation ~ CAPEX (maintenance capex),
    so EBIT ~ EBITDA - Depreciation ~ EBITDA - CAPEX.
    """
    cashflows: list[dict] = []
    revenue = current_annual_revenue

    for year_idx, growth in enumerate(growth_rates, start=1):
        revenue = revenue * (1 + growth)
        ebitda = revenue * (ebitda_margin_pct / 100.0)
        capex = revenue * (capex_pct_revenue / 100.0)
        depreciation = capex  # maintenance capex assumption
        ebit = ebitda - depreciation
        taxes = max(0, ebit * (tax_rate_pct / 100.0))
        nopat = ebit - taxes
        change_wc = revenue * (working_capital_pct_revenue / 100.0) * growth
        fcf = nopat + depreciation - capex - change_wc

        cashflows.append(
            {
                "year": year_idx,
                "revenue_brl": round(revenue, 2),
                "growth_rate": round(growth, 4),
                "ebitda_brl": round(ebitda, 2),
                "ebitda_margin_pct": round(ebitda_margin_pct, 2),
                "capex_brl": round(capex, 2),
                "ebit_brl": round(ebit, 2),
                "taxes_brl": round(taxes, 2),
                "nopat_brl": round(nopat, 2),
                "change_wc_brl": round(change_wc, 2),
                "fcf_brl": round(fcf, 2),
            }
        )

    return cashflows


def _terminal_value(
    final_year_fcf: float,
    terminal_growth_pct: float,
    wacc_pct: float,
) -> float:
    """Terminal value using Gordon Growth Model (perpetuity growth).

    TV = FCF_final * (1 + g) / (WACC - g)
    """
    g = terminal_growth_pct / 100.0
    wacc = wacc_pct / 100.0

    if wacc <= g:
        # Fallback: use exit multiple method (5x final EBITDA equivalent)
        return final_year_fcf * 10
    return final_year_fcf * (1 + g) / (wacc - g)


def _discount_to_pv(
    cashflows: list[dict],
    terminal_value: float,
    wacc_pct: float,
) -> float:
    """Discount projected cash flows and terminal value to present value."""
    wacc = wacc_pct / 100.0
    pv_sum = 0.0

    for cf in cashflows:
        year = cf["year"]
        discount_factor = 1 / ((1 + wacc) ** year)
        pv_sum += cf["fcf_brl"] * discount_factor

    # Terminal value discounted from the final projection year
    final_year = cashflows[-1]["year"]
    tv_discount = 1 / ((1 + wacc) ** final_year)
    pv_sum += terminal_value * tv_discount

    return pv_sum


def _build_sensitivity_table(
    cashflows: list[dict],
    base_wacc: float,
    base_terminal_growth: float,
    net_debt: float,
) -> dict:
    """Build a WACC x terminal growth sensitivity matrix.

    Returns enterprise values for a grid of WACC and growth assumptions.
    """
    wacc_steps = [base_wacc - 2, base_wacc - 1, base_wacc, base_wacc + 1, base_wacc + 2]
    growth_steps = [
        base_terminal_growth - 1,
        base_terminal_growth - 0.5,
        base_terminal_growth,
        base_terminal_growth + 0.5,
        base_terminal_growth + 1,
    ]

    table: dict = {
        "wacc_values": [round(w, 1) for w in wacc_steps],
        "growth_values": [round(g, 1) for g in growth_steps],
        "enterprise_values": [],
    }

    final_fcf = cashflows[-1]["fcf_brl"]

    for wacc in wacc_steps:
        row: list[float] = []
        for growth in growth_steps:
            if wacc / 100.0 <= growth / 100.0:
                row.append(0.0)  # invalid combination
                continue
            tv = _terminal_value(final_fcf, growth, wacc)
            ev = _discount_to_pv(cashflows, tv, wacc)
            equity = max(0, ev - net_debt)
            row.append(round(equity, 2))
        table["enterprise_values"].append(row)

    return table


def calculate(
    monthly_revenue_brl: float,
    revenue_growth_rates: list[float] | None = None,
    ebitda_margin_pct: float = 30.0,
    capex_pct_revenue: float = 15.0,
    wacc_pct: float = 14.0,
    terminal_growth_pct: float = 3.0,
    net_debt_brl: float = 0,
) -> DCFValuation:
    """Calculate DCF valuation with 5-year projection.

    Parameters
    ----------
    monthly_revenue_brl : float
        Current gross monthly recurring revenue in BRL.
    revenue_growth_rates : list[float] | None
        Year-over-year growth rates for 5 years. Defaults to declining rates.
    ebitda_margin_pct : float
        EBITDA margin as percentage (e.g. 30.0 for 30%).
    capex_pct_revenue : float
        Capital expenditure as percentage of revenue (e.g. 15.0).
    wacc_pct : float
        Weighted average cost of capital as percentage (e.g. 14.0).
    terminal_growth_pct : float
        Perpetuity growth rate for terminal value (e.g. 3.0 for 3%).
    net_debt_brl : float
        Net debt (debt minus cash). Subtracted from EV to get equity value.

    Returns
    -------
    DCFValuation
    """
    if revenue_growth_rates is None:
        revenue_growth_rates = list(DEFAULT_GROWTH_RATES)

    # Ensure we have exactly 5 years
    while len(revenue_growth_rates) < 5:
        revenue_growth_rates.append(revenue_growth_rates[-1] if revenue_growth_rates else 0.04)
    revenue_growth_rates = revenue_growth_rates[:5]

    current_annual_revenue = monthly_revenue_brl * 12

    # Project cash flows
    projected_cashflows = _project_cashflows(
        current_annual_revenue=current_annual_revenue,
        growth_rates=revenue_growth_rates,
        ebitda_margin_pct=ebitda_margin_pct,
        capex_pct_revenue=capex_pct_revenue,
    )

    # Terminal value
    final_fcf = projected_cashflows[-1]["fcf_brl"]
    tv = _terminal_value(final_fcf, terminal_growth_pct, wacc_pct)

    # Enterprise value (PV of FCFs + PV of terminal value)
    enterprise_value = _discount_to_pv(projected_cashflows, tv, wacc_pct)

    # Equity value
    equity_value = max(0, enterprise_value - net_debt_brl)

    # Sensitivity table
    sensitivity = _build_sensitivity_table(
        cashflows=projected_cashflows,
        base_wacc=wacc_pct,
        base_terminal_growth=terminal_growth_pct,
        net_debt=net_debt_brl,
    )

    return DCFValuation(
        projected_cashflows=projected_cashflows,
        terminal_value_brl=round(tv, 2),
        wacc_pct=round(wacc_pct, 2),
        enterprise_value_brl=round(enterprise_value, 2),
        equity_value_brl=round(equity_value, 2),
        net_debt_brl=round(net_debt_brl, 2),
        sensitivity_table=sensitivity,
    )
