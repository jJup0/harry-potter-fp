#!/usr/bin/env python3
"""Extract Prisoner of Azkaban transcript from script-o-rama HTML."""

import re
from html.parser import HTMLParser


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self.current = ""
        self.skip = 0
        self.in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True
        if tag in ("script", "style"):
            self.skip += 1
        if self.in_body and tag in ("p", "br", "li", "h2", "h3", "td", "tr"):
            if self.current.strip():
                self.lines.append(self.current.strip())
            self.current = ""

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip > 0:
            self.skip -= 1
        if self.in_body and tag in ("p", "div", "td"):
            if self.current.strip():
                self.lines.append(self.current.strip())
            self.current = ""

    def handle_data(self, data):
        if self.in_body and self.skip == 0:
            self.current += data

    def get_text(self):
        if self.current.strip():
            self.lines.append(self.current.strip())
        return "\n".join(self.lines)


with open("/tmp/hp3_raw.html") as f:
    html = f.read()

p = Extractor()
p.feed(html)
text = p.get_text()

# Remove header/footer noise
text = re.sub(r".*?Lumos Maxima\.", "Lumos Maxima.", text, count=1, flags=re.DOTALL)
text = re.sub(r"Special help by.*$", "", text, flags=re.DOTALL)
text = text.strip()

with open(
    "/Users/jroi/personal/harry-potter-aitor/data/raw/screenplays/3_prisoner_of_azkaban.txt",
    "w",
) as f:
    f.write(text)

print(f"Saved: {len(text)} chars")
