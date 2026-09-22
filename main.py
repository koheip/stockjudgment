import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf

try:
    from typesafe import TypeSafe
except ImportError:
    TypeSafe = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = TypeSafe(api_key=os.getenv("TYPESAFE_API_KEY")) if TypeSafe and os.getenv("TYPESAFE_API_KEY") else None


@app.get("/")
def root():
    return {"message": "10-year stock prediction API is running"}


@app.get("/predict/{ticker}")
def predict_stock(ticker: str):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="10y", auto_adjust=False)

    if hist.empty or len(hist) < 2:
        return {"error": "指定された銘柄が見つかりませんでした"}

    close = hist["Close"].dropna()
    start_price = float(close.iloc[0])
    latest_price = float(close.iloc[-1])
    start_date = close.index[0]
    end_date = close.index[-1]
    years_elapsed = max((end_date - start_date).days / 365.25, 1.0)

    annualized_return = ((latest_price / start_price) ** (1 / years_elapsed) - 1) * 100
    future_years = 10
    projected_price_10y = latest_price * ((1 + annualized_return / 100) ** future_years)
    projected_change_pct = ((projected_price_10y - latest_price) / latest_price) * 100

    news_items = stock.news if isinstance(stock.news, list) else []
    news_titles = [item.get("title", "") for item in news_items[:3] if isinstance(item, dict)] if news_items else ["関連ニュースなし"]

    state = {
        "ticker": ticker,
        "latest_close_price": latest_price,
        "start_close_price": start_price,
        "annualized_return_percent": round(annualized_return, 2),
        "projected_price_10y": round(projected_price_10y, 2),
        "projected_change_percent_10y": round(projected_change_pct, 2),
        "recent_news": news_titles,
    }

    if client is None:
        direction = "UP" if projected_change_pct >= 0 else "DOWN" if projected_change_pct < 0 else "NEUTRAL"
        return {
            "ticker": ticker,
            "latest_price": latest_price,
            "prediction_horizon_years": 10,
            "projected_price_10y": round(projected_price_10y, 2),
            "projected_change_pct": round(projected_change_pct, 2),
            "prediction": {
                "mode": "fallback",
                "choice": direction,
                "reason": "TYPESAFE_API_KEY が未設定のため、10年間の成長率から簡易予測をしています。",
                "state": state,
            },
        }

    response = client.evaluate(
        model="jev-1.13.0",
        state=state,
        questions=[
            {
                "type": "choice",
                "question": f"Stateのデータに基づき、{ticker} の10年後の株価動向として最も確率が高い選択肢を選んでください。",
                "options": {
                    "UP": "10年後に上昇する",
                    "DOWN": "10年後に下落する",
                    "NEUTRAL": "10年後にほぼ横ばい",
                },
            }
        ],
    )

    return {
        "ticker": ticker,
        "latest_price": latest_price,
        "prediction_horizon_years": 10,
        "projected_price_10y": round(projected_price_10y, 2),
        "projected_change_pct": round(projected_change_pct, 2),
        "prediction": response,
    }