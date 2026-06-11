import os

INDIA_LOCATIONS = ["India","Bangalore","Hyderabad","Pune","Mumbai","Chennai","Delhi","Noida","Gurgaon"]
SN_ROLES = ["ServiceNow Developer","ServiceNow Administrator","ServiceNow Architect","ServiceNow Consultant","ServiceNow ITSM","ITSM","ServiceNow Itom","custom app","HRSD","SecOps","GRC","ITOM","ITBM","CSM","FSM","ServiceNow Developer","ServiceNow consultant"]

OUTPUT_CSV  = "output/candidates.csv"
OUTPUT_JSON = "output/candidates.json"

REQUEST_DELAY_SECONDS  = 2
MAX_RESULTS_PER_SOURCE = 50
REQUEST_TIMEOUT        = 15

# Reads from environment variables — set these in Fly.io dashboard
SERPAPI_KEYS = [
    k.strip()
    for k in [
        os.getenv("SERPAPI_KEY_1", ""),
        os.getenv("SERPAPI_KEY_2", ""),
        os.getenv("SERPAPI_KEY_3", ""),
    ]
    if k.strip()
]