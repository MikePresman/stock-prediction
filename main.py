import os
import datetime
import pandas as pd
import json
import openai
from playwright.sync_api import sync_playwright

from openai import OpenAI
client = OpenAI()  # Uses OPENAI_API_KEY from env

# === CONFIGURATION ===
openai.api_key = os.getenv("OPENAI_API_KEY")  # Load from env var for safety
EXCEL_FILE = "prediction_history.xlsx"
TODAY = datetime.date.today()
REAL_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
USERS = {
    "elonmusk": "https://x.com/elonmusk",
    "realDonaldTrump": "https://x.com/realDonaldTrump",
}

SIMULATED_PRICES = {
    "TSLA": 180.0, "F": 12.4, "XOM": 105.0, "GM": 45.0, "RIVN": 11.3,
    "NVDA": 130.0, "MSFT": 420.0, "GOOGL": 175.0, "DJT": 35.0,
}

def scrape_tweets(url, max_count=5):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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

def get_stock_predictions_from_summary(summary):
    prompt = f"""
Given this feud summary:
\"\"\"{summary}\"\"\"

Suggest 2-3 publicly traded companies whose stock might be impacted.
For each, explain briefly why and suggest BUY, SELL, or HOLD.
Respond in JSON format like:
[
  {{
    "ticker": "TSLA",
    "action": "BUY",
    "reason": "Elon is defending EVs while Trump criticizes them, increasing attention on Tesla."
  }}
]
"""
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

def update_excel(predictions):
    df_today = pd.DataFrame(predictions)
    if os.path.exists(EXCEL_FILE):
        df_history = pd.read_excel(EXCEL_FILE)
        df_combined = pd.concat([df_history, df_today], ignore_index=True)
    else:
        df_combined = df_today
    df_combined.to_excel(EXCEL_FILE, index=False)
    print(f"✅ Logged {len(predictions)} predictions to {EXCEL_FILE}.")

def main():
    all_tweets = {}
    for name, url in USERS.items():
        print(f"Scraping tweets from {name}...")
        tweets = scrape_tweets(url)
        all_tweets[name] = tweets

    summary = get_feud_summary(all_tweets["elonmusk"], all_tweets["realDonaldTrump"])
    print("\n📄 Feud Summary:", summary)

    predictions = get_stock_predictions_from_summary(summary)
    print("\n📈 Predictions:")
    for p in predictions:
        print(f"  {p['ticker']} - {p['action']} ({p['reason']})")

    # Add extra fields
    for p in predictions:
        p["price"] = SIMULATED_PRICES.get(p["ticker"], 0.0)
        p["sentiment"] = "n/a"
        p["date"] = TODAY

    update_excel(predictions)

if __name__ == "__main__":
    main()

