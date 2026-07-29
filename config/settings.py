import os
from dotenv import load_dotenv

load_dotenv()

INDIA_LOCATIONS = ["Mumbai", "Pune", "Bangalore", "Hyderabad", "Chennai", "Delhi", "Noida", "Gurugram", "remote India"]
SN_ROLES = ["ServiceNow developer", "ServiceNow ITSM", "ServiceNow ITOM", "ServiceNow CSM", "ServiceNow admin", "ServiceNow architect", "ServiceNow integration developer", "ServiceNow platform engineer"]

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

# End of settings