import json, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.database import init_db, SessionLocal, Candidate
from api.routes import router

app = FastAPI(title="SN Sourcer API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")
app.mount("/dashboard", StaticFiles(directory="dashboard"), name="dashboard")

@app.get("/")
def root():
    return FileResponse("dashboard/index.html")

def import_candidates_json():
    json_path = "output/candidates.json"
    if not os.path.exists(json_path):
        return
    with open(json_path,"r",encoding="utf-8", errors="replace") as f:
        candidates = json.load(f)
    db = SessionLocal()
    added = 0
    try:
        for c in candidates:
            url = c.get("linkedin_url","").strip()
            if not url: continue
            if db.query(Candidate).filter(Candidate.linkedin_url==url).first():
                continue
            db.add(Candidate(
                name=c.get("name",""), title=c.get("title",""),
                linkedin_url=url, location=c.get("location",""),
                role_searched=c.get("role_searched",""),
                open_to_work=bool(c.get("open_to_work",True)),
                snippet=c.get("snippet",""),
            ))
            added += 1
        db.commit()
        print(f"  [import] {added} new candidates imported.")
    except Exception as e:
        db.rollback(); print(f"  [import] Error: {e}")
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    print("\n  Initialising DB...")
    init_db()
    print("  Importing candidates.json...")
    import_candidates_json()
    print("  Dashboard → http://localhost:8000\n")