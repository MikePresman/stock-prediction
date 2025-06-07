import os
import datetime
import pandas as pd
import yfinance as yf
import json
from playwright.sync_api import sync_playwright
from openai import OpenAI

client = OpenAI()

EXCEL_FILE = "prediction_history.xlsx"
TODAY = datetime.date.today()
REAL_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
USERS = {
    "elonmusk": "https://x.com/elonmusk",
    "realDonaldTrump": "https://x.com/realDonaldTrump",
}

def get_current_price(ticker):
    try:
        current_data = yf.Ticker(ticker).history(period="1d")
        if not current_data.empty:
            return round(current_data["Close"].iloc[-1], 2)
    except Exception as e:
        print(f"⚠️ Error fetching price for {ticker}: {e}")
    return None

def scrape_tweets(url, max_count=5):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=REAL_USER_AGENT)
        page = context.new_page()

        print(f"🔍 Visiting: {url}")
        page.goto(url, timeout=60000)

        for _ in range(3):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1500)

        try:
            page.wait_for_selector('[data-testid="tweetText"]', timeout=10000)
            tweet_elements = page.query_selector_all('[data-testid="tweetText"]')
            tweets = [el.inner_text().strip() for el in tweet_elements[:max_count]]
            print(f"✅ Found {len(tweets)} tweets.")
        except Exception as e:
            print(f"⚠️ Could not find tweets: {e}")
            tweets = []

        browser.close()
        return tweets

def evaluate_past_performance():
    if not os.path.exists(EXCEL_FILE):
        return None

    df = pd.read_excel(EXCEL_FILE)
    df = df[df['ticker'] != "EVALUATION"]
    if df.empty:
        return None

    df = df.sort_values(by="date", ascending=False)
    recent = df.head(50)
    if recent.empty:
        return None

    evaluation_notes = []
    correct_count = 0
    total_count = 0

    for _, row in recent.iterrows():
        ticker = row["ticker"]
        original_price = row["price"]
        action = row["action"]

        latest_price = get_current_price(ticker)
        if latest_price is None:
            evaluation_notes.append(f"⚠️ Could not fetch data for {ticker}.")
            continue

        total_count += 1
        if action == "BUY" and latest_price > original_price:
            correct_count += 1
            evaluation_notes.append(f"✅ BUY {ticker} was good. {original_price} → {latest_price:.2f}")
        elif action == "SELL" and latest_price < original_price:
            correct_count += 1
            evaluation_notes.append(f"✅ SELL {ticker} was good. {original_price} → {latest_price:.2f}")
        else:
            evaluation_notes.append(f"❌ {action} {ticker} was bad. {original_price} → {latest_price:.2f}")

    accuracy = round(100 * correct_count / total_count, 2) if total_count > 0 else 0.0
    summary = f"Evaluated {total_count} recent predictions: {correct_count} correct ({accuracy}%)."

    summary_row = {
        "ticker": "EVALUATION",
        "action": "SUMMARY",
        "sentiment": accuracy,
        "price": 0,
        "date": TODAY,
        "reason": summary + "\n" + "\n".join(evaluation_notes[:5])
    }

    df_all = pd.read_excel(EXCEL_FILE)
    df_all = pd.concat([df_all, pd.DataFrame([summary_row])], ignore_index=True)
    df_all.to_excel(EXCEL_FILE, index=False)

    return summary + "\nUse this evaluation to improve today's predictions."

def get_feud_summary(elon_tweets, trump_tweets):
    prompt = f"""
Elon Musk and Donald Trump posted these tweets today:

Elon:
{chr(10).join(elon_tweets)}

Donald:
{chr(10).join(trump_tweets)}

Summarize the main conflict or debate between them in 1-2 sentences.
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a financial analyst and stock strategist."},
            {"role": "user", "content": prompt}
        ]
    )
    return res.choices[0].message.content.strip()

def get_stock_predictions_from_summary(summary, evaluation_context):
    prompt = (
        "Based on the following recent performance summary:\n"
        f"{evaluation_context}\n\n"
        "And this feud summary:\n"
        f"{summary}\n\n"
        "Suggest 2-3 publicly traded companies whose stock might be impacted.\n"
        "For each, explain briefly why and suggest BUY, SELL, or HOLD.\n"
        "Respond in JSON format like:\n"
        "[\n"
        "  {\n"
        "    \"ticker\": \"TSLA\",\n"
        "    \"action\": \"BUY\",\n"
        "    \"reason\": \"Elon is defending EVs while Trump criticizes them, increasing attention on Tesla.\"\n"
        "  }\n"
        "]"
    )
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a financial analyst and stock strategist."},
            {"role": "user", "content": prompt}
        ]
    )
    try:
        return json.loads(res.choices[0].message.content)
    except Exception as e:
        print("❌ Error parsing GPT response:", e)
        return []

def log_today_predictions(predictions):
    rows = []
    for p in predictions:
        current_price = get_current_price(p["ticker"])
        rows.append({
            "ticker": p["ticker"],
            "action": p["action"],
            "sentiment": p.get("sentiment", "n/a"),
            "price": current_price or 0,
            "date": TODAY,
            "reason": p.get("reason", "")
        })

    if os.path.exists(EXCEL_FILE):
        df_history = pd.read_excel(EXCEL_FILE)
        df_combined = pd.concat([df_history, pd.DataFrame(rows)], ignore_index=True)
    else:
        df_combined = pd.DataFrame(rows)

    df_combined.to_excel(EXCEL_FILE, index=False)
    print(f"✅ Logged {len(rows)} predictions to {EXCEL_FILE}.")

def main():
    evaluation_summary = evaluate_past_performance() or "No past performance available."

    all_tweets = {}
    for name, url in USERS.items():
        print(f"Scraping tweets from {name}...")
        tweets = scrape_tweets(url)
        all_tweets[name] = tweets

    feud_summary = get_feud_summary(all_tweets.get("elonmusk", []), all_tweets.get("realDonaldTrump", []))
    print("\n📄 Feud Summary:\n", feud_summary)

    predictions = get_stock_predictions_from_summary(feud_summary, evaluation_summary)
    print("\n📈 Predictions:")
    for p in predictions:
        print(f"  {p['ticker']} - {p['action']} ({p['reason']})")

    log_today_predictions(predictions)

if __name__ == "__main__":
    main()
