import time
import feedparser

sources = {
    "iDnes": "https://www.idnes.cz/rss.asp?c=A000000000",
    "Novinky": "https://www.novinky.cz/rss/",
    "Seznam": "https://www.seznamzpravy.cz/rss",
}

def get_titles():
    for name, url in sources.items():
        feed = feedparser.parse(url)
        print(f"{name}: {feed.entries[0].title}")

if __name__ == "__main__":
    get_titles()
