# Oficiální Playwright Python image s už předinstalovaným Chromiem
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Nastavíme pracovní složku uvnitř kontejneru
WORKDIR /app

# Zkopíruj celý obsah projektu do /app
COPY . /app

# Nainstaluj Python balíčky
RUN pip install --no-cache-dir -r requirements.txt

# Spusť Flask app přes Gunicorn na portu 10000
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
