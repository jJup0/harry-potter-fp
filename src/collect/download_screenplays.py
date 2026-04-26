#!/usr/bin/env python3
"""Download Harry Potter film transcripts via fandom MediaWiki API."""
import json
import os
import re
import urllib.request
from html.parser import HTMLParser

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "screenplays")
os.makedirs(DEST, exist_ok=True)

# (wiki subdomain, page title) — using best available source per film
FILMS = {
    "1_philosophers_stone": ("movies.fandom.com", "Harry_Potter_and_the_Philosopher's_Stone/Transcript"),
    "2_chamber_of_secrets": ("movies.fandom.com", "Harry_Potter_and_the_Chamber_of_Secrets/Transcript"),
    "3_prisoner_of_azkaban": ("the-jh-movie-collection-official.fandom.com", "Harry_Potter_and_the_Prisoner_of_Azkaban_(film)/Transcript"),
    "4_goblet_of_fire": ("movies.fandom.com", "Harry_Potter_and_the_Goblet_of_Fire/Transcript"),
    "5_order_of_the_phoenix": ("movies.fandom.com", "Harry_Potter_and_the_Order_of_the_Phoenix/Transcript"),
    "6_half_blood_prince": ("movies.fandom.com", "Harry_Potter_and_the_Half-Blood_Prince/Transcript"),
    "7_deathly_hallows_p1": ("movies.fandom.com", "Harry_Potter_and_the_Deathly_Hallows_–_Part_1/Transcript"),
    "8_deathly_hallows_p2": ("movies.fandom.com", "Harry_Potter_and_the_Deathly_Hallows_–_Part_2/Transcript"),
}

# Fallback sources if primary fails
FALLBACKS = {
    "3_prisoner_of_azkaban": ("warnerbros.fandom.com", "Harry_Potter_and_the_Prisoner_of_Azkaban_(film)/Transcript"),
    "4_goblet_of_fire": ("warnerbros.fandom.com", "Harry_Potter_and_the_Goblet_of_Fire_(film)/Transcript"),
    "5_order_of_the_phoenix": ("warnerbros.fandom.com", "Harry_Potter_and_the_Order_of_the_Phoenix_(film)/Transcript"),
    "6_half_blood_prince": ("warnerbros.fandom.com", "Harry_Potter_and_the_Half-Blood_Prince/Transcript"),
}


class SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self.current = ""
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "br", "li", "h2", "h3", "h4", "tr", "dd", "dt"):
            if self.current.strip():
                self.lines.append(self.current.strip())
            self.current = ""

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip > 0:
            self.skip -= 1
        if tag in ("p", "li", "h2", "h3", "h4", "div", "dd", "dt"):
            if self.current.strip():
                self.lines.append(self.current.strip())
            self.current = ""

    def handle_data(self, data):
        if self.skip == 0:
            self.current += data

    def get_text(self):
        if self.current.strip():
            self.lines.append(self.current.strip())
        return "\n".join(self.lines)


def fetch_via_api(wiki_domain, page_title):
    encoded_title = urllib.request.quote(page_title, safe="/:_'–")
    api_url = f"https://{wiki_domain}/api.php?action=parse&page={encoded_title}&prop=text&format=json&redirects=1"
    req = urllib.request.Request(api_url, headers={"User-Agent": "HarryPotterCorpusBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "parse" not in data:
        raise ValueError(f"No parse result: {list(data.keys())}")

    html = data["parse"]["text"]["*"]
    parser = SimpleHTMLTextExtractor()
    parser.feed(html)
    text = parser.get_text()
    text = re.sub(r"\[edit\]", "", text)
    text = re.sub(r"Categories:.*$", "", text, flags=re.DOTALL)
    return text


def download_transcript(key, wiki_domain, page_title):
    dest_file = os.path.join(DEST, f"{key}.txt")
    if os.path.exists(dest_file):
        print(f"SKIP {key} (already exists)")
        return True

    print(f"Downloading {key} from {wiki_domain}...")
    try:
        text = fetch_via_api(wiki_domain, page_title)
        if len(text) < 500:
            print(f"  WARNING: only {len(text)} chars, likely stub/redirect")
            return False
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  -> {len(text)} chars")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


if __name__ == "__main__":
    for key in sorted(FILMS):
        wiki_domain, page_title = FILMS[key]
        ok = download_transcript(key, wiki_domain, page_title)
        if not ok and key in FALLBACKS:
            fb_domain, fb_title = FALLBACKS[key]
            print(f"  Trying fallback: {fb_domain}...")
            download_transcript(key, fb_domain, fb_title)

    print(f"\nDone. Transcripts in {DEST}:")
    for f in sorted(os.listdir(DEST)):
        path = os.path.join(DEST, f)
        print(f"  {f}: {os.path.getsize(path):,} bytes")
