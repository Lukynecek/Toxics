from flask import Flask, request, render_template, redirect, url_for
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from transformers import pipeline
import time
import numpy as np

app = Flask(__name__)
classifier = pipeline("text-classification", model="unitary/toxic-bert", top_k=None)

def scroll_to_bottom(driver, pause=1, max_scrolls=10):
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    while scrolls < max_scrolls:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scrolls += 1

def extract_text_universal(driver):
    # Pro jistotu vždy scrollni
    scroll_to_bottom(driver, pause=1.5, max_scrolls=30)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    text_blocks = []

    # Nejčastější tagy s textem (funguje i na 4chan, blogy, zpravodajství)
    selectors = [
        "article",
        "p",
        "blockquote",
        "div.postMessage",
        "div[class*='post']",
        "div[class*='text']",
        "div[class*='content']",
        "div[class*='body']",
    ]

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                try:
                    txt = el.text.strip()
                    if txt and len(txt) > 30:
                        text_blocks.append(txt)
                except StaleElementReferenceException:
                    continue
        except Exception:
            continue

    # Záchrana: celý innerText dokumentu
    try:
        raw = driver.execute_script("return document.body.innerText")
        if raw and len(raw.strip()) > 100:
            text_blocks.append(raw.strip())
    except:
        pass

    # Odstranění duplicit a balastu
    seen = set()
    final_texts = []
    blacklist = ["cookies", "login", "subscribe", "advertisement", "accept", "sign up", "privacy", "footer", "terms", "ads", "policy"]

    for t in text_blocks:
        lower = t.lower()
        if t not in seen and not any(b in lower for b in blacklist):
            seen.add(t)
            final_texts.append(t)

    return "\n\n".join(final_texts)




def extract_text_4chan(driver):
    text_blocks = []
    scroll_to_bottom(driver, pause=1.5, max_scrolls=30)

    try:
        posts = driver.find_elements(By.CSS_SELECTOR, "div.postMessage")
        for post in posts:
            try:
                txt = post.text.strip()
                if txt and txt not in text_blocks:
                    text_blocks.append(txt)
            except StaleElementReferenceException:
                continue
    except Exception:
        pass

    try:
        blockquotes = driver.find_elements(By.TAG_NAME, "blockquote")
        for bq in blockquotes:
            try:
                txt = bq.text.strip()
                if txt and txt not in text_blocks:
                    text_blocks.append(txt)
            except StaleElementReferenceException:
                continue
    except Exception:
        pass

    unique_texts = []
    seen = set()
    for t in text_blocks:
        if t and len(t) > 30 and t not in seen:
            unique_texts.append(t)
            seen.add(t)

    return "\n\n".join(unique_texts)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form["url"]
        return redirect(url_for("analyze", url=url))
    return render_template("index.html")

@app.route("/analyze")
def analyze():
    url = request.args.get("url")

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")

    driver = webdriver.Chrome(service=Service(), options=options)

    try:
        driver.get(url)
        text = extract_text_universal(driver)
    finally:
        driver.quit()

    chunks = [chunk.strip()[:500] for chunk in text.split("\n\n") if len(chunk.strip()) > 30]
    if not chunks:
        return render_template("result.html", scores={"error": "Nepodařilo se získat žádný text."}, url=url)

    results = classifier(chunks, batch_size=4)

    scores_per_label = {}
    for analysis in results:
        for label_score in analysis:
            label = label_score['label']
            score = label_score['score']
            scores_per_label.setdefault(label, []).append(score)

    averaged_scores = {label: round(np.mean(scores), 3) for label, scores in scores_per_label.items()}
    return render_template("result.html", scores=averaged_scores, url=url)


if __name__ == "__main__":
    app.run(debug=True)
