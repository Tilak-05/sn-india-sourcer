import os, time, requests
from config.settings import (
    INDIA_LOCATIONS, SN_ROLES,
    REQUEST_DELAY_SECONDS, MAX_RESULTS_PER_SOURCE, REQUEST_TIMEOUT,
    SERPAPI_KEYS,
)

SERPAPI_ENDPOINT = "https://serpapi.com/search"
SEEN_URLS_FILE   = "output/seen_urls.txt"

def load_seen_urls() -> set:
    if not os.path.exists(SEEN_URLS_FILE):
        return set()
    with open(SEEN_URLS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen_url(url: str):
    os.makedirs("output", exist_ok=True)
    with open(SEEN_URLS_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

class QuotaExhausted(Exception):
    pass

class KeyManager:
    def __init__(self, keys):
        self.keys = keys; self.index = 0
    def current(self): return self.keys[self.index]
    def switch_to_next(self):
        self.index += 1
        if self.index >= len(self.keys):
            return False
        return True
    def has_key(self): return self.index < len(self.keys)

def build_query(role, location):
    return f'site:linkedin.com/in "{role}" "{location}" ("open to work" OR "#opentowork")'

def serpapi_search(query, start, key):
    params = {"engine":"google","q":query,"start":start,"num":10,"api_key":key}
    resp = requests.get(SERPAPI_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT)
    if resp.status_code == 429:
        raise QuotaExhausted()
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        msg = data["error"].lower()
        if "out of searches" in msg or "plan" in msg:
            raise QuotaExhausted()
        raise Exception("SerpAPI error: " + data["error"])
    return data.get("organic_results", [])

def parse_results(results, role, location):
    candidates = []
    for r in results:
        link = r.get("link",""); title = r.get("title",""); snippet = r.get("snippet","")
        if "linkedin.com/in/" not in link: continue
        if "open to work" not in snippet.lower() and "opentowork" not in snippet.lower(): continue
        clean = title.replace(" | LinkedIn","").strip()
        parts = [p.strip() for p in clean.split(" - ")]
        candidates.append({
            "name": parts[0] if parts else clean,
            "title": parts[1] if len(parts)>1 else "",
            "linkedin_url": link, "location": location,
            "role_searched": role, "open_to_work": True, "snippet": snippet,
        })
    return candidates

def scrape(max_results=MAX_RESULTS_PER_SOURCE, progress_callback=None):
    if not SERPAPI_KEYS:
        return []
    seen_urls = load_seen_urls()
    km = KeyManager(SERPAPI_KEYS)
    new_candidates = []
    for role in SN_ROLES[:4]:
        for location in INDIA_LOCATIONS[:5]:
            if not km.has_key(): return new_candidates
            query = build_query(role, location)
            if progress_callback:
                progress_callback(f"Searching: {role} | {location}")
            for start in range(0, 30, 10):
                if not km.has_key(): return new_candidates
                try:
                    results = serpapi_search(query, start, km.current())
                except QuotaExhausted:
                    if not km.switch_to_next(): return new_candidates
                    try: results = serpapi_search(query, start, km.current())
                    except: break
                except Exception: break
                if not results: break
                for c in parse_results(results, role, location):
                    url = c["linkedin_url"]
                    if url in seen_urls: continue
                    seen_urls.add(url); save_seen_url(url)
                    new_candidates.append(c)
                if len(new_candidates) >= max_results: return new_candidates
                time.sleep(REQUEST_DELAY_SECONDS)
    return new_candidates
