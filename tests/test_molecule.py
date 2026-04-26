import requests
import json

# 测试分子合成API
target = "BrC1=C2CCCOC2=NC=C1"
url = "http://localhost:8000/route"

payload = {
    "target": target,
    "top_k": 3,
    "debug": False
}

headers = {
    "Content-Type": "application/json"
}

print(f"Test molecule: {target}")
print(f"API URL: {url}")
print("Sending request...")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=300)

    if response.status_code == 200:
        result = response.json()
        print("\n[SUCCESS] API call successful!")
        print(f"Status code: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")

        # 检查是否有合成路线
        if "synthesis_route" in result and result["synthesis_route"]:
            print("\n[SUCCESS] Synthesis route generated!")
        elif "routes" in result and len(result["routes"]) > 0:
            print(f"\n[SUCCESS] {len(result['routes'])} routes generated!")
        else:
            print("\n[FAILED] No synthesis routes generated")
    else:
        print(f"\n[FAILED] API call failed")
        print(f"Status code: {response.status_code}")
        print(f"Error: {response.text}")

except Exception as e:
    print(f"\n[ERROR] Request failed: {str(e)}")
