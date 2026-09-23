"""Collect dated evidence without inventing missing financial values."""
import logging
import math
import time
from numbers import Real
import pandas as pd
from curl_cffi import requests as curl_requests

logger = logging.getLogger("uvicorn.error")
TIMESERIES_URL = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{}"


def number(value):
    return float(value) if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) else None


def annual_records(frame, fields):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    records = []
    for date in sorted(frame.columns, reverse=True)[:5]:
        record = {"period_end": str(date.date())}
        for name in fields:
            if name in frame.index:
                value = number(frame.loc[name, date])
                if value is not None:
                    record[name] = value
        if len(record) > 1:
            records.append(record)
    return records


def timeseries_records(ticker, sources):
    """Annual statements straight from Yahoo's timeseries endpoint.

    Unlike quoteSummary this endpoint needs no cookie/crumb, so it keeps working on cloud
    hosts where yfinance's crumb handshake fails. It also reports the statement currency."""
    now = int(time.time())
    types = {"annual" + name.replace(" ", ""): (key, name) for key, _, fields in sources for name in fields}
    response = curl_requests.get(TIMESERIES_URL.format(ticker), impersonate="chrome", timeout=20,
                                 params=dict(symbol=ticker, type=",".join(types), period1=now - 7 * 365 * 86400, period2=now))
    response.raise_for_status()
    periods, currency = {}, None
    for series in (response.json().get("timeseries") or {}).get("result") or []:
        kind = ((series.get("meta") or {}).get("type") or [None])[0]
        if kind not in types:
            continue
        key, name = types[kind]
        for point in series.get(kind) or []:
            value = number(((point or {}).get("reportedValue") or {}).get("raw"))
            if value is None or not point.get("asOfDate"):
                continue
            periods.setdefault(key, {}).setdefault(point["asOfDate"], {})[name] = value
            currency = currency or (point.get("currencyCode") if name != "Diluted EPS" else None)
    records = {key: [dict(period_end=date, **values) for date, values in sorted(dates.items(), reverse=True)[:5]]
               for key, dates in periods.items()}
    return records, currency


def collect_evidence(stock, ticker=None):
    result = {"income": [], "cashflow": [], "balance": [], "price_history": {}, "warnings": [], "financial_currency": None}
    sources = [
        ("income", "get_income_stmt", ["Total Revenue", "Operating Income", "Net Income", "Diluted EPS"]),
        ("cashflow", "get_cash_flow", ["Operating Cash Flow", "Free Cash Flow", "Capital Expenditure"]),
        ("balance", "get_balance_sheet", ["Total Debt", "Stockholders Equity", "Cash And Cash Equivalents"]),
    ]
    direct = {}
    if ticker:
        try:
            direct, result["financial_currency"] = timeseries_records(ticker, sources)
        except Exception as exc:
            logger.warning("timeseries fetch failed for %s: %r", ticker, exc)
    for key, method, fields in sources:
        result[key] = direct.get(key, [])
        if not result[key]:
            try:
                result[key] = annual_records(getattr(stock, method)(freq="yearly", pretty=True), fields)
            except Exception as exc:
                logger.warning("%s failed for %s: %r", method, ticker, exc)
        if not result[key]:
            result["warnings"].append(f"{key}: 年次データ取得不可")
    try:
        history = stock.history(period="10y", interval="1mo", auto_adjust=False, timeout=15)
        if isinstance(history, pd.DataFrame) and "Close" in history:
            close = history["Close"].dropna()
            close = close[close.map(lambda v: number(v) is not None and v > 0)]
            if len(close) >= 12:
                years = (close.index[-1] - close.index[0]).days / 365.25
                if years > 0:
                    result["price_history"] = dict(start=str(close.index[0].date()), end=str(close.index[-1].date()),
                        years=round(years, 2), price_cagr=number((float(close.iloc[-1]) / float(close.iloc[0])) ** (1 / years) - 1),
                        note="月次Closeによる過去の価格変化。配当を含まず、将来への外挿は禁止。")
    except Exception:
        pass
    return result


def evidence_coverage(screening, evidence):
    groups = set()
    mapping = {"revenueGrowth": "growth", "earningsGrowth": "growth", "operatingMargins": "profitability",
               "returnOnEquity": "profitability", "freeCashflow": "cashflow", "debtToEquity": "balance", "trailingPE": "valuation"}
    for metric in screening["metrics"]:
        if metric["value"] is not None:
            groups.add(mapping[metric["key"]])
    income = evidence.get("income", [])
    if sum("Total Revenue" in r for r in income) >= 2 or sum("Net Income" in r for r in income) >= 2:
        groups.add("growth")
    if any("Operating Income" in r or "Net Income" in r for r in income):
        groups.add("profitability")
    if any("Free Cash Flow" in r or "Operating Cash Flow" in r for r in evidence.get("cashflow", [])):
        groups.add("cashflow")
    if any("Total Debt" in r and "Stockholders Equity" in r for r in evidence.get("balance", [])):
        groups.add("balance")
    # Price momentum alone is never sufficient fundamental evidence.
    return sorted(groups)
