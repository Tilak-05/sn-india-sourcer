"""
DuckDuckGo-based x-ray scraper — completely free, no API key needed.

Searches three sources:
  1. LinkedIn profiles (site:linkedin.com/in ...)
  2. Resume PDFs (filetype:pdf ...)
  3. GitHub profiles (site:github.com ...)

Uses the `ddgs` library with date filtering for last-month results.
"""

import os, time, re
from config.settings import (
    INDIA_LOCATIONS, SN_ROLES,
    DDG_MAX_RESULTS, DDG_TIMELIMIT, DDG_REGION, DDG_SEARCH_DELAY,
)

SEEN_URLS_FILE = "output/seen_urls.txt"


def load_seen_urls() -> set:
    if not os.path.exists(SEEN_URLS_FILE):
        return set()
    with open(SEEN_URLS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_seen_url(url: str):
    os.makedirs("output", exist_ok=True)
    with open(SEEN_URLS_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")


def sanitize(text):
    """Strip non-UTF-8 bytes from any string."""
    if not isinstance(text, str):
        return str(text) if text else ""
    return text.encode("utf-8", errors="replace").decode("utf-8")


# ── Query builders ──────────────────────────────────────────────

def build_linkedin_query(role, location):
    # DuckDuckGo struggles with complex OR logic, so we keep it simpler
    return f'site:linkedin.com/in "{role}" "{location}" "open to work"'


def build_resume_query(role, location):
    return f'"{role}" "resume" "{location}" filetype:pdf'


def build_github_query(role, location):
    return f'site:github.com "{role}" "{location}"'


QUERY_BUILDERS = {
    "linkedin":   build_linkedin_query,
    "resume_pdf": build_resume_query,
    "github":     build_github_query,
}


# ── Result parsers ──────────────────────────────────────────────

def parse_linkedin_result(r, role, location):
    """Parse a DuckDuckGo result from a LinkedIn x-ray search."""
    link = r.get("href", "") or r.get("link", "")
    title = r.get("title", "")
    snippet = r.get("body", "") or r.get("snippet", "")

    if "linkedin.com/in/" not in link:
        return None

    # Check for open-to-work signals
    combined = (title + " " + snippet).lower()
    if "open to work" not in combined and "opentowork" not in combined:
        return None

    clean = title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
    parts = [p.strip() for p in clean.split(" - ")]

    return {
        "name": sanitize(parts[0] if parts else clean),
        "title": sanitize(parts[1] if len(parts) > 1 else ""),
        "linkedin_url": sanitize(link),
        "location": sanitize(location),
        "role_searched": sanitize(role),
        "open_to_work": True,
        "snippet": sanitize(snippet),
        "source": "linkedin",
    }


def parse_resume_result(r, role, location):
    """Parse a DuckDuckGo result from a resume PDF search."""
    link = r.get("href", "") or r.get("link", "")
    title = r.get("title", "")
    snippet = r.get("body", "") or r.get("snippet", "")

    if not link:
        return None

    # Try to extract a name from the title
    name = title
    # Common patterns: "Name - Resume", "Resume - Name", "Name_Resume.pdf"
    for sep in [" - ", " | ", " – ", "_"]:
        if sep in name:
            parts = name.split(sep)
            # Pick the part that looks most like a name (shortest, no common keywords)
            for p in parts:
                p = p.strip()
                lower = p.lower()
                if lower not in ("resume", "cv", "pdf", "curriculum vitae", "") and len(p) < 60:
                    name = p
                    break
            break

    name = re.sub(r'\.pdf$', '', name, flags=re.IGNORECASE).strip()

    return {
        "name": sanitize(name),
        "title": sanitize(role),
        "linkedin_url": sanitize(link),   # reuse field for any URL
        "location": sanitize(location),
        "role_searched": sanitize(role),
        "open_to_work": True,
        "snippet": sanitize(snippet[:300]),
        "source": "resume_pdf",
    }


def parse_github_result(r, role, location):
    """Parse a DuckDuckGo result from a GitHub search."""
    link = r.get("href", "") or r.get("link", "")
    title = r.get("title", "")
    snippet = r.get("body", "") or r.get("snippet", "")

    if "github.com" not in link:
        return None

    # Try to get username / name from title
    clean = title.replace(" · GitHub", "").replace(" - GitHub", "").strip()
    parts = [p.strip() for p in clean.split(" - ")]
    name = parts[0] if parts else clean

    return {
        "name": sanitize(name),
        "title": sanitize(parts[1] if len(parts) > 1 else role),
        "linkedin_url": sanitize(link),   # reuse field for profile URL
        "location": sanitize(location),
        "role_searched": sanitize(role),
        "open_to_work": True,
        "snippet": sanitize(snippet[:300]),
        "source": "github",
    }


PARSERS = {
    "linkedin":   parse_linkedin_result,
    "resume_pdf": parse_resume_result,
    "github":     parse_github_result,
}


# ── Main scraper ────────────────────────────────────────────────

def scrape(
    sources=None,
    max_results=DDG_MAX_RESULTS,
    timelimit=DDG_TIMELIMIT,
    fresh=False,
    progress_callback=None,
    roles=None,
):
    """
    Scrape candidates using DuckDuckGo search.

    Args:
        sources: list of sources to search (default: uses settings.DDG_SOURCES)
        max_results: max results per query
        timelimit: 'd'=day, 'w'=week, 'm'=month, 'y'=year
        fresh: if True, ignore seen_urls.txt (get all results)
        progress_callback: optional fn(msg) for logging progress
    """
    from ddgs import DDGS
    from config.settings import DDG_SOURCES

    if sources is None:
        sources = DDG_SOURCES

    seen_urls = set() if fresh else load_seen_urls()
    new_candidates = []

    def log(msg):
        if progress_callback:
            progress_callback(msg)

    log(f"🔍 DuckDuckGo search — sources: {', '.join(sources)}")
    log(f"   Time filter: last {'day' if timelimit == 'd' else 'week' if timelimit == 'w' else 'month' if timelimit == 'm' else 'year'}")
    if fresh:
        log("   🔄 Fresh mode ON — ignoring previously seen URLs")

    with DDGS() as ddgs:
        for source in sources:
            builder = QUERY_BUILDERS.get(source)
            parser = PARSERS.get(source)
            if not builder or not parser:
                log(f"⚠️  Unknown source: {source}")
                continue

            log(f"\n── {source.upper()} ──")

            # 3 roles * 3 locations = 9 searches
            for role in (roles or SN_ROLES[:3]):
                for location in INDIA_LOCATIONS[:3]:
                    query = builder(role, location)
                    log(f"→ {role} | {location}")

                    try:
                        results = ddgs.text(
                            query,
                            timelimit=timelimit,
                            region=DDG_REGION,
                            max_results=max_results,
                        )

                        if not results:
                            continue

                        found = 0
                        for r in results:
                            candidate = parser(r, role, location)
                            if not candidate:
                                continue

                            url = candidate.get("linkedin_url", "")
                            if url in seen_urls:
                                continue

                            seen_urls.add(url)
                            if not fresh:
                                save_seen_url(url)
                            new_candidates.append(candidate)
                            found += 1

                        if found:
                            log(f"  + {found} candidates")

                    except Exception as e:
                        err = str(e).lower()
                        if "ratelimit" in err or "429" in err:
                            log(f"  ⚠️  Rate limited — waiting 10s...")
                            time.sleep(10)
                        else:
                            log(f"  ⚠️  Error: {e}")

                    time.sleep(DDG_SEARCH_DELAY)

    log(f"\n✅ DDG scrape complete — {len(new_candidates)} new candidates found")
    return new_candidates
