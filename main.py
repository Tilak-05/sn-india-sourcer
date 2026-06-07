#!/usr/bin/env python3
"""
Scraper-only entry point (no dashboard).
Usage: python main.py
"""
import json, sys, os
import pandas as pd
from colorama import Fore, Style, init
sys.path.insert(0, os.path.dirname(__file__))
from scrapers import linkedin_xray
from config.settings import OUTPUT_CSV, OUTPUT_JSON
init(autoreset=True)

OUTPUT_FIELDS = ["name","title","linkedin_url","location","role_searched","open_to_work","snippet"]

def sync_to_db(candidates):
    try:
        from api.database import init_db, SessionLocal, Candidate
        init_db(); db = SessionLocal(); added = 0
        try:
            for c in candidates:
                url = c.get("linkedin_url","").strip()
                if not url: continue
                if db.query(Candidate).filter(Candidate.linkedin_url==url).first(): continue
                db.add(Candidate(name=c.get("name",""),title=c.get("title",""),
                    linkedin_url=url,location=c.get("location",""),
                    role_searched=c.get("role_searched",""),
                    open_to_work=bool(c.get("open_to_work",True)),snippet=c.get("snippet","")))
                added += 1
            db.commit()
            print(f"{Fore.GREEN}DB saved → {added} new candidates{Style.RESET_ALL}")
        except Exception as e:
            db.rollback(); print(f"{Fore.RED}DB error: {e}{Style.RESET_ALL}")
        finally: db.close()
    except ImportError:
        print(f"{Fore.YELLOW}DB sync skipped{Style.RESET_ALL}")

def run():
    print(f"\n{Fore.CYAN}{'='*54}\n  ServiceNow India — Open To Work Sourcer\n{'='*54}{Style.RESET_ALL}\n")
    try: results = linkedin_xray.scrape()
    except Exception as e:
        print(f"{Fore.RED}Scraper failed: {e}{Style.RESET_ALL}"); return
    if not results:
        print(f"{Fore.RED}No new candidates found.{Style.RESET_ALL}"); return
    seen=set(); unique=[]
    for c in results:
        url=c.get("linkedin_url","")
        if url not in seen: seen.add(url); unique.append(c)
    print(f"\n{Fore.CYAN}Total unique: {len(unique)}{Style.RESET_ALL}\n")
    df=pd.DataFrame(unique)[OUTPUT_FIELDS]; df.to_csv(OUTPUT_CSV,index=False,encoding="utf-8")
    print(f"{Fore.GREEN}CSV → {OUTPUT_CSV}{Style.RESET_ALL}")
    with open(OUTPUT_JSON,"w",encoding="utf-8") as f: json.dump(unique,f,ensure_ascii=False,indent=2)
    print(f"{Fore.GREEN}JSON → {OUTPUT_JSON}{Style.RESET_ALL}")
    sync_to_db(unique)
    print(f"\n{Fore.CYAN}── Top 5 ─────────────────{Style.RESET_ALL}")
    for i,c in enumerate(unique[:5],1):
        print(f"\n  {Fore.YELLOW}#{i} {c['name']}{Style.RESET_ALL}\n     {c.get('title')}\n     {c.get('location')}\n     {c.get('linkedin_url')}")
    print(f"\n{Fore.CYAN}Done! Dashboard → http://localhost:8000{Style.RESET_ALL}\n")

if __name__=="__main__": run()
