import os
import json
import requests
import anthropic
from datetime import datetime, timezone


FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]
NEWS_API_KEY = os.environ["NEWS_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ZAPIER_WEBHOOK_URL = os.environ["ZAPIER_WEBHOOK_URL"]

MARKET_SYMBOLS = {
    "S&P 500": "SPY",
    "Nasdaq 100": "QQQ",
    "Dow Jones": "DIA",
    "Russell 2000": "IWM",
    "Bitcoin": "BINANCE:BTCUSDT",
    "Ethereum": "BINANCE:ETHUSDT",
    "Gold": "OANDA:XAUUSD",
    "Oil (WTI)": "OANDA:WTIUSD",
    "EUR/USD": "OANDA:EURUSD",
    "USD/JPY": "OANDA:USDJPY",
}


def get_quote(symbol: str) -> dict:
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    resp = requests.get(url, timeout=10)
    if resp.ok:
        d = resp.json()
        return {"price": d.get("c"), "change_pct": round(d.get("dp", 0), 2)}
    return {}


def get_market_quotes() -> dict:
    quotes = {}
    for name, symbol in MARKET_SYMBOLS.items():
        quotes[name] = get_quote(symbol)
    return quotes


def get_finnhub_news(category: str, limit: int = 8) -> list:
    url = f"https://finnhub.io/api/v1/news?category={category}&token={FINNHUB_API_KEY}"
    resp = requests.get(url, timeout=10)
    if resp.ok:
        items = resp.json()[:limit]
        return [{"headline": a.get("headline"), "summary": a.get("summary", "")[:200]} for a in items]
    return []


def get_top_world_news(limit: int = 12) -> list:
    url = (
        f"https://newsapi.org/v2/top-headlines"
        f"?language=en&pageSize={limit}&apiKey={NEWS_API_KEY}"
    )
    resp = requests.get(url, timeout=10)
    if resp.ok:
        articles = resp.json().get("articles", [])
        return [
            {
                "title": a["title"],
                "source": a["source"]["name"],
                "description": (a.get("description") or "")[:200],
            }
            for a in articles
        ]
    return []


def build_briefing(quotes: dict, financial_news: list, economic_news: list, world_news: list) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    now = datetime.now(timezone.utc).strftime("%B %d, %Y  %H:%M UTC")

    context = f"""
BRIEFING TIME: {now}

=== MARKET SNAPSHOT ===
{json.dumps(quotes, indent=2)}

=== FINANCIAL MARKET NEWS ===
{json.dumps(financial_news, indent=2)}

=== ECONOMIC NEWS ===
{json.dumps(economic_news, indent=2)}

=== TOP WORLD NEWS ===
{json.dumps(world_news, indent=2)}
"""

    prompt = f"""You are a sharp financial analyst and global news editor producing a WhatsApp briefing.

{context}

Write a concise, high-signal briefing with exactly these sections — use WhatsApp formatting (*bold*, _italic_, no markdown headers):

*📊 MARKETS — {now}*
Summarise the key moves (up/down %) and the main driver behind them. 2-3 sentences max.

*💹 ECONOMY*
Most important macroeconomic development right now (rate decisions, inflation, GDP, central bank signals). 2-3 sentences.

*🌍 WORLD*
Top 3-4 global stories (political, social, geopolitical). One sentence each.

*🔮 WATCH*
1-2 things to monitor in the next 5 hours and why.

Rules:
- Total length: 300-450 words
- No jargon — clear enough for a smart non-specialist
- Lead with what matters most, cut the rest
- Do NOT say "As of {now}" repeatedly — say it once at the top
"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


def send_to_whatsapp(text: str) -> None:
    payload = {
        "message": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    resp = requests.post(ZAPIER_WEBHOOK_URL, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Delivered to Zapier — HTTP {resp.status_code}")


def main() -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting briefing run")

    print("  Fetching market quotes...")
    quotes = get_market_quotes()

    print("  Fetching financial news...")
    financial_news = get_finnhub_news("general")

    print("  Fetching economic news...")
    economic_news = get_finnhub_news("economic")

    print("  Fetching world headlines...")
    world_news = get_top_world_news()

    print("  Generating briefing with Claude...")
    briefing = build_briefing(quotes, financial_news, economic_news, world_news)

    print("  Sending to WhatsApp via Zapier...")
    send_to_whatsapp(briefing)

    print("Done.\n")
    print("--- BRIEFING PREVIEW ---")
    print(briefing)


if __name__ == "__main__":
    main()
