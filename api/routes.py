from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from api.database import get_db, Candidate

router = APIRouter()

# Shared fetch state
fetch_state = {"running": False, "log": [], "added": 0, "error": None}


def sanitize(text):
    """Strip non-UTF-8 bytes from any string to prevent JSON encoding errors."""
    if not isinstance(text, str):
        return text
    return text.encode("utf-8", errors="replace").decode("utf-8")


def run_fetch():
    import sys, os, json
    import pandas as pd
    import requests as req
    sys.path.insert(0, os.getcwd())
    fetch_state["running"] = True
    fetch_state["log"] = []
    fetch_state["added"] = 0
    fetch_state["error"] = None

    def log(msg):
        fetch_state["log"].append(msg)

    try:
        from config.settings import SERPAPI_KEYS, INDIA_LOCATIONS, SN_ROLES, REQUEST_DELAY_SECONDS
        from api.database import SessionLocal, Candidate as C, init_db
        import time

        if not SERPAPI_KEYS:
            raise Exception("No SERPAPI_KEYS configured in config/settings.py")

        log(f"Checking {len(SERPAPI_KEYS)} SerpAPI key(s)...")
        valid_keys = []
        for key in SERPAPI_KEYS:
            try:
                r = req.get("https://serpapi.com/account", params={"api_key": key}, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    plan_limit = data.get("plan_searches_left", "?")
                    log(f"✅ Key valid — {plan_limit} searches remaining this month")
                    valid_keys.append(key)
                elif r.status_code == 403:
                    log(f"❌ Key invalid or expired (403)")
                else:
                    log(f"⚠️  Key check returned {r.status_code}")
            except Exception as e:
                log(f"⚠️  Key check failed: {e}")

        if not valid_keys:
            raise Exception(
                "All SerpAPI keys are invalid or expired. "
                "Get a free key at https://serpapi.com → paste into config/settings.py SERPAPI_KEYS"
            )

        log(f"{len(valid_keys)} valid key(s) found. Starting scrape...")

        seen_file = "output/seen_urls.txt"
        seen_urls = set()
        if os.path.exists(seen_file):
            with open(seen_file) as f:
                seen_urls = set(l.strip() for l in f if l.strip())
        log(f"Previously seen: {len(seen_urls)} URLs (will skip these)")

        key_idx = 0
        new_candidates = []

        for role in SN_ROLES[:4]:
            for loc in INDIA_LOCATIONS[:5]:
                if key_idx >= len(valid_keys):
                    log("All key quotas exhausted."); break
                query = f'site:linkedin.com/in "{role}" "{loc}" ("open to work" OR "#opentowork")'
                log(f"→ {role} | {loc}")

                for start in range(0, 30, 10):
                    if key_idx >= len(valid_keys): break
                    try:
                        params = {"engine": "google", "q": query, "start": start, "num": 10,
                                  "api_key": valid_keys[key_idx]}
                        resp = req.get("https://serpapi.com/search", params=params, timeout=15)
                        if resp.status_code == 429:
                            log(f"  Quota hit on key {key_idx+1}, switching...")
                            key_idx += 1; break
                        resp.raise_for_status()
                        data = resp.json()
                        if "error" in data:
                            err = data["error"].lower()
                            if "out of searches" in err or "plan" in err:
                                log(f"  Key {key_idx+1} quota exhausted, switching...")
                                key_idx += 1; break
                            log(f"  API error: {data['error']}"); break
                        results = data.get("organic_results", [])
                        if not results: break

                        for r in results:
                            link = r.get("link", ""); snippet = r.get("snippet", "")
                            title_raw = r.get("title", "")
                            if "linkedin.com/in/" not in link: continue
                            if "open to work" not in snippet.lower() and "opentowork" not in snippet.lower(): continue
                            if link in seen_urls: continue
                            seen_urls.add(link)
                            with open(seen_file, "a") as f: f.write(link + "\n")
                            clean = title_raw.replace(" | LinkedIn", "").strip()
                            parts = [p.strip() for p in clean.split(" - ")]
                            new_candidates.append({
                                "name": sanitize(parts[0] if parts else clean),
                                "title": sanitize(parts[1] if len(parts) > 1 else ""),
                                "linkedin_url": sanitize(link), "location": sanitize(loc),
                                "role_searched": sanitize(role), "open_to_work": True,
                                "snippet": sanitize(snippet),
                            })
                            log(f"  + {parts[0] if parts else clean}")
                        time.sleep(REQUEST_DELAY_SECONDS)
                    except Exception as e:
                        log(f"  Request error: {e}"); break

        log(f"Scrape complete. {len(new_candidates)} new candidates found.")

        init_db()
        db = SessionLocal()
        added = 0
        try:
            for c in new_candidates:
                url = c.get("linkedin_url", "").strip()
                if not url: continue
                if db.query(C).filter(C.linkedin_url == url).first(): continue
                db.add(C(
                    name=c.get("name", ""), title=c.get("title", ""),
                    linkedin_url=url, location=c.get("location", ""),
                    role_searched=c.get("role_searched", ""),
                    open_to_work=bool(c.get("open_to_work", True)),
                    snippet=c.get("snippet", ""),
                ))
                added += 1
            db.commit()
            fetch_state["added"] = added
            log(f"✅ Saved {added} new candidates to database.")

            os.makedirs("output", exist_ok=True)
            all_rows = db.query(C).all()
            data = [{"name": r.name, "title": r.title, "linkedin_url": r.linkedin_url,
                     "location": r.location, "role_searched": r.role_searched,
                     "open_to_work": r.open_to_work, "snippet": r.snippet} for r in all_rows]
            pd.DataFrame(data).to_csv("output/candidates.csv", index=False, encoding="utf-8")
            log(f"📁 Exported {len(data)} total to CSV.")
        except Exception as e:
            db.rollback(); raise e
        finally:
            db.close()

    except Exception as e:
        fetch_state["error"] = str(e)
        fetch_state["log"].append(f"❌ {e}")
    finally:
        fetch_state["running"] = False


def run_import_json():
    import os, json
    fetch_state["running"] = True
    fetch_state["log"] = []
    fetch_state["added"] = 0
    fetch_state["error"] = None

    def log(msg):
        fetch_state["log"].append(msg)

    try:
        from api.database import SessionLocal, Candidate as C, init_db
        json_path = "output/candidates.json"
        if not os.path.exists(json_path):
            raise Exception("output/candidates.json not found")

        with open(json_path, "r", encoding="utf-8") as f:
            candidates = json.load(f)
        log(f"Loaded {len(candidates)} candidates from candidates.json")

        init_db()
        db = SessionLocal()
        added = 0
        try:
            for c in candidates:
                url = c.get("linkedin_url", "").strip()
                if not url: continue
                if db.query(C).filter(C.linkedin_url == url).first(): continue
                db.add(C(
                    name=c.get("name", ""), title=c.get("title", ""),
                    linkedin_url=url, location=c.get("location", ""),
                    role_searched=c.get("role_searched", ""),
                    open_to_work=bool(c.get("open_to_work", True)),
                    snippet=c.get("snippet", ""),
                ))
                added += 1
            db.commit()
            fetch_state["added"] = added
            log(f"✅ Synced! {added} new candidates added to DB.")
        except Exception as e:
            db.rollback(); raise e
        finally:
            db.close()

    except Exception as e:
        fetch_state["error"] = str(e)
        fetch_state["log"].append(f"❌ {e}")
    finally:
        fetch_state["running"] = False


@router.post("/fetch")
def trigger_fetch(background_tasks: BackgroundTasks):
    if fetch_state["running"]:
        return {"status": "already_running"}
    background_tasks.add_task(run_fetch)
    return {"status": "started"}

@router.post("/import-json")
def trigger_import(background_tasks: BackgroundTasks):
    if fetch_state["running"]:
        return {"status": "already_running"}
    background_tasks.add_task(run_import_json)
    return {"status": "started"}

@router.get("/fetch/status")
def fetch_status():
    return fetch_state


@router.get("/candidates")
def get_candidates(
    db: Session = Depends(get_db),
    search: Optional[str]   = Query(None),
    location: Optional[str] = Query(None),
    role: Optional[str]     = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    q = db.query(Candidate)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(
            func.lower(Candidate.name).like(term) |
            func.lower(Candidate.title).like(term) |
            func.lower(Candidate.snippet).like(term)
        )
    if location and location != "all":
        q = q.filter(func.lower(Candidate.location) == location.lower())
    if role and role != "all":
        q = q.filter(func.lower(Candidate.role_searched) == role.lower())
    total = q.count()
    items = q.order_by(Candidate.id.desc()).offset(skip).limit(limit).all()
    return {
        "total": total, "skip": skip, "limit": limit,
        "data": [{
            "id": c.id, "name": c.name, "title": c.title,
            "linkedin_url": c.linkedin_url, "location": c.location,
            "role_searched": c.role_searched, "open_to_work": c.open_to_work,
            "snippet": c.snippet,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        } for c in items],
    }


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Candidate).count()
    by_location = db.query(Candidate.location, func.count(Candidate.id).label("count"))\
        .group_by(Candidate.location).order_by(func.count(Candidate.id).desc()).all()
    by_role = db.query(Candidate.role_searched, func.count(Candidate.id).label("count"))\
        .group_by(Candidate.role_searched).order_by(func.count(Candidate.id).desc()).all()
    return {
        "total": total,
        "by_location": [{"location": r.location, "count": r.count} for r in by_location],
        "by_role": [{"role": r.role_searched, "count": r.count} for r in by_role],
    }


@router.get("/filters")
def get_filters(db: Session = Depends(get_db)):
    locations = [r[0] for r in db.query(Candidate.location).distinct().order_by(Candidate.location).all() if r[0]]
    roles = [r[0] for r in db.query(Candidate.role_searched).distinct().order_by(Candidate.role_searched).all() if r[0]]
    return {"locations": locations, "roles": roles}


@router.delete("/candidates/{candidate_id}")
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(c); db.commit()
    return {"deleted": True}

@router.get("/export-csv")
def export_csv(db: Session = Depends(get_db)):
    import csv, io
    rows = db.query(Candidate).order_by(Candidate.id.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","name","title","linkedin_url","location","role_searched","open_to_work","snippet","created_at"])
    for c in rows:
        writer.writerow([
            c.id, c.name, c.title, c.linkedin_url, c.location,
            c.role_searched, c.open_to_work, c.snippet,
            c.created_at.isoformat() if c.created_at else ""
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=candidates.csv"}
    )