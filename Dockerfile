FROM python:3.12-slim

# Build v3 - 长正文自动拆分
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxcb1 libxkbcommon0 libx11-6 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir flask pillow pyyaml playwright

RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

COPY . .

# 预热 Chromium，避免第一次请求时下载/初始化超时
RUN python -c "from playwright.sync_api import sync_playwright; \
    p = sync_playwright().start(); \
    browser = p.chromium.launch(headless=True); \
    browser.close(); \
    p.stop()"

ENV HOST=0.0.0.0
ENV PORT=8080

CMD python -c "from app import app; import os; app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)"
