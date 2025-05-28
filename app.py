from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from transformers import pipeline
import time
import numpy as np
import re

app = Flask(__name__)

# Inicializace klasifikátoru toxicity pomocí předtrénovaného modelu
classifier = pipeline("text-classification", model="unitary/toxic-bert", top_k=None)

# Funkce pro automatické posouvání na konec stránky kvůli načtení dynamického obsahu
def scroll_to_bottom(driver, pause=1, max_scrolls=10):
    last_h = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        time.sleep(pause)
        new_h = driver.execute_script("return document.body.scrollHeight")
        if new_h == last_h:
            break
        last_h = new_h

# Obecný extraktor textu z různých webových stránek (např. zpravodajské weby, blogy)
def extract_text_universal(driver):
    scroll_to_bottom(driver, pause=1.5, max_scrolls=30)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    text_blocks = []

    # Výběr běžných selektorů obsahujících text
    selectors = [
        "article", "p", "blockquote",
        "div.postMessage",
        "div[class*='post']",
        "div[class*='text']",
        "div[class*='content']",
        "div[class*='body']",
    ]

    for sel in selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    t = el.text.strip()
                    if t and len(t) > 30:
                        text_blocks.append(t)
                except StaleElementReferenceException:
                    continue
        except:
            continue

    # Záložní možnost: získání celého textu z dokumentu
    try:
        raw = driver.execute_script("return document.body.innerText")
        if raw and len(raw.strip()) > 100:
            text_blocks.append(raw.strip())
    except:
        pass

    # Odstranění duplicit a balastního textu
    seen, final = set(), []
    blacklist = ["cookies","login","subscribe","advertisement",
                 "accept","sign up","privacy","footer","terms","ads","policy"]
    for t in text_blocks:
        low = t.lower()
        if t not in seen and not any(b in low for b in blacklist):
            seen.add(t)
            final.append(t)
    return "\n\n".join(final)

# Specializovaný extraktor textu pro 4chan (zpracovává div.postMessage a blockquote)
def extract_text_4chan(driver):
    scroll_to_bottom(driver, pause=1.5, max_scrolls=30)
    text_blocks = []

    # Získání textu z postMessage bloků
    try:
        for post in driver.find_elements(By.CSS_SELECTOR, "div.postMessage"):
            t = post.text.strip()
            if t and len(t) > 30:
                text_blocks.append(t)
    except:
        pass

    # Získání textu z blockquote prvků
    try:
        for bq in driver.find_elements(By.TAG_NAME, "blockquote"):
            t = bq.text.strip()
            if t and len(t) > 30:
                text_blocks.append(t)
    except:
        pass

    # Odstranění duplicit
    seen, final = set(), []
    for t in text_blocks:
        if t not in seen:
            seen.add(t)
            final.append(t)
    return "\n\n".join(final)

def get_color(score):
    if score < 0.33:
        return "green"
    elif score < 0.66:
        return "orange"
    else:
        return "red"


# API endpoint pro analýzu toxicity textu z URL
@app.route("/api/analyze")
def api_analyze():
    url = request.args.get("url","").strip()
    if not url:
        return jsonify(error="No URL provided"), 400

    # Nastavení pro bezhlavý režim Chromu (neotevírá okno prohlížeče)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0")
    driver = webdriver.Chrome(service=Service(), options=options)

    try:
        driver.get(url)

        # Detekce, jestli je to stránka z 4chanu, a podle toho volba extrakční funkce
        if re.search(r"\b4chan\.org\b", url):
            text = extract_text_4chan(driver)
        else:
            text = extract_text_universal(driver)
    finally:
        driver.quit()

    # Rozdělení textu do menších bloků (chunků) pro klasifikaci
    chunks = [c.strip()[:500] for c in text.split("\n\n") if len(c.strip()) > 30]
    if not chunks:
        return jsonify(error="Failed to extract text"), 422

    # Klasifikace jednotlivých bloků
    results = classifier(chunks, batch_size=4)

    # Agregace skóre podle kategorií (toxicity, insult, obscene, atd.)
    scores = {}
    for analysis in results:
        for item in analysis:
            lbl = item["label"]
            scores.setdefault(lbl, []).append(item["score"])

    # Průměrování výsledků a zaokrouhlení na tři desetinná místa
    averaged = {lbl: round(float(np.mean(vals)), 3) for lbl, vals in scores.items()}
    
        # Přidání barvy ke každé kategorii
    output = {}
    for label, val in averaged.items():
        output[label] = {
            "value": round(val, 3),
            "color": get_color(val)
        }

    return jsonify(averaged)

# Spuštění Flask serveru
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
