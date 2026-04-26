import requests
import json

# 测试API健康状态
def test_health():
    url = "http://localhost:8000/health"
    print(f"Testing health endpoint: {url}")
    try:
        response = requests.get(url, timeout=30)
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("SUCCESS: Health check passed")
            print(f"Response: {response.json()}")
        else:
            print("FAILED: Health check failed")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"ERROR: Request failed - {e}")

# 测试分子合成
def test_synthesis():
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
    
    print(f"\nTesting molecule synthesis for: {target}")
    print(f"API URL: {url}")
    print("Sending request...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("SUCCESS: API call successful")
            print(f"Response keys: {list(result.keys())}")
            
            # 检查是否有合成路线
            if "synthesis_route" in result and result["synthesis_route"]:
                print("SUCCESS: Synthesis route generated")
            elif "routes" in result and len(result["routes"]) > 0:
                print(f"SUCCESS: {len(result['routes'])} routes generated")
            else:
                print("FAILED: No synthesis routes generated")
        else:
            print("FAILED: API call failed")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"ERROR: Request failed - {e}")

if __name__ == "__main__":
    test_health()
    test_synthesis()
