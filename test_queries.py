import requests, json
import sys

def test_query(q, tbs=None):
    from config.settings import SERPAPI_KEYS
    params = {'engine': 'google', 'q': q, 'api_key': SERPAPI_KEYS[0]}
    if tbs: params['tbs'] = tbs
    r = requests.get('https://serpapi.com/search', params=params)
    data = r.json()
    if 'error' in data: print(f"Error: {data['error']}")
    else: print(f"Results: {len(data.get('organic_results', []))}")

print("Test 1: Normal query with tbs=qdr:m")
test_query('site:linkedin.com/in ServiceNow admin Mumbai -jobs -hiring -"we are hiring" -recruiter ("open to work" OR "#opentowork")', 'qdr:m')

print("Test 2: Normal query without tbs")
test_query('site:linkedin.com/in ServiceNow admin Mumbai -jobs -hiring -"we are hiring" -recruiter ("open to work" OR "#opentowork")')

print("Test 3: Simplest query")
test_query('site:linkedin.com/in ServiceNow Mumbai')

print("Test 4: Just open to work")
test_query('site:linkedin.com/in ServiceNow Mumbai "open to work"')
