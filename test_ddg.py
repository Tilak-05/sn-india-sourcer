from ddgs import DDGS
ddgs = DDGS()
print("Test 1: Normal query")
try:
    res = ddgs.text('site:linkedin.com/in "ServiceNow Developer" "Bangalore" ("open to work" OR "#opentowork")', region='in-en', max_results=5)
    print(res)
except Exception as e:
    print(e)

print("\nTest 2: Looser query")
try:
    res2 = ddgs.text('site:linkedin.com/in ServiceNow Bangalore "open to work"', region='in-en', max_results=5)
    print(res2)
except Exception as e:
    print(e)
