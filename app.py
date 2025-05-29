from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from transformers import pipeline
import numpy as np
import gunicorn
import re

app = Flask(__name__)
classifier = pipeline("text-classification", model="unitary/toxic-bert", top_k=None)

# Posouvání na konec stránky kvůli JS obsahu
def scroll_to_bottom(page, pause=1000, max_scrolls=10):
    for _ in range(max_scrolls):
        previous_height = page.evaluate("() => document.body.scrollHeight")
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause)
        new_height = page.evaluate("() => document.body.scrollHeight")
        if new_height == previous_height:
            break

# Univerzální extrakce textu (4chan i ostatní weby)
def extract_text(page, url):
    scroll_to_bottom(page, pause=1500, max_scrolls=30)
    text_blocks = []

    selectors = [
        "article", "p", "blockquote",
        "div.postMessage",
        "div[class*='post']",
        "div[class*='text']",
        "div[class*='content']",
        "div[class*='body']"
    ]

    for sel in selectors:
        try:
            elements = page.query_selector_all(sel)
            for el in elements:
                t = el.inner_text().strip()
                if t and len(t) > 30:
                    text_blocks.append(t)
        except:
            continue

    # Fallback: celý obsah <body>
    try:
        raw = page.inner_text("body").strip()
        if raw and len(raw) > 100:
            text_blocks.append(raw)
    except:
        pass

    # Čištění a deduplikace
    seen, final = set(), []
    blacklist = ["cookies", "login", "subscribe", "advertisement", "accept", "sign up", "privacy", "footer", "terms", "ads", "policy"]
    for t in text_blocks:
        low = t.lower()
        if t not in seen and not any(b in low for b in blacklist):
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

@app.route("/api/analyze")
def api_analyze():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify(error="No URL provided"), 400

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0")
        try:
            page.goto(url, timeout=60000)
            text = extract_text(page, url)
        except Exception as e:
            browser.close()
            return jsonify(error=str(e)), 500
        browser.close()

    chunks = [c.strip()[:500] for c in text.split("\n\n") if len(c.strip()) > 30]
    if not chunks:
        return jsonify(error="Failed to extract text"), 422

    results = classifier(chunks, batch_size=4)

    scores = {}
    for analysis in results:
        for item in analysis:
            lbl = item["label"]
            scores.setdefault(lbl, []).append(item["score"])

    averaged = {lbl: round(float(np.mean(vals)), 3) for lbl, vals in scores.items()}
    output = {label: {"value": val, "color": get_color(val)} for label, val in averaged.items()}

    return jsonify(output)

@app.route('/')
def health_check():
    return 'OK', 200

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
