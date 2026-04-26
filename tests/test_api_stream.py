import requests
import json

# 测试 /route/stream 端点
target = "BrC1=C2CCCOC2=NC=C1"
url = "http://localhost:8000/route/stream"

payload = {
    "target": target,
    "top_k": 1,
    "debug": True
}

headers = {
    "Content-Type": "application/json"
}

print(f"Testing /route/stream endpoint for molecule: {target}")
print(f"API URL: {url}")
print("Sending request...")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=300, stream=True)

    if response.status_code == 200:
        print(f"Status code: {response.status_code}")
        print("Streaming response received successfully")

        # 读取流式数据
        buffer = ''
        event_count = 0
        
        for line in response.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    data_str = decoded[6:].strip()
                    if data_str:
                        event_count += 1
                        print(f"Event {event_count}: {data_str[:100]}...")
                        
                        # 检查是否有错误信息
                        if 'error' in data_str.lower():
                            print(f"Error found: {data_str}")

        print(f"\nTotal events received: {event_count}")
        print("✅ API endpoint is working!")

    else:
        print(f"Failed with status code: {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"Error: {e}")
