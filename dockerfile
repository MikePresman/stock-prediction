FROM python:3.11-slim

WORKDIR /app

# Install system packages
RUN apt-get update && apt-get install -y \
    wget gnupg2 curl unzip fonts-liberation \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libgtk-3-0 libxss1 libasound2 libxshmfence-dev \
    libgbm-dev libxrandr2 xdg-utils \
    && apt-get clean

# Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright + browsers
RUN pip install playwright && \
    playwright install --with-deps

COPY . .

CMD ["python", "scrape_tweets_playwright.py"]

