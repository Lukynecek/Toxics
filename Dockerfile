FROM python:3.11-slim

WORKDIR /app

# Nainstaluj závislosti Playwrightu (hlavně ty systémový knihovny)
RUN apt-get update && apt-get install -y \
    wget \
    libglib2.0-0 \
    libnss3 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libxss1 \
    libasound2 \
    libxshmfence1 \
    libgbm1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libu2f-udev \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libdrm2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libxinerama1 \
    libx11-xcb1 \
    libxtst6 \
    libpci3 \
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Zkopíruj celý projekt do kontejneru
COPY . .

# Nainstaluj pythoní závislosti a playwright prohlížeče
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && playwright install --with-deps

EXPOSE 10000

# Spusť server přes gunicorn na portu 10000
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
