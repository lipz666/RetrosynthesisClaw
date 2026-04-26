import requests
import json

# 测试chain/stream端点，这是前端实际使用的端点
target = "BrC1=C2CCCOC2=NC=C1"
url = "http://localhost:8000/chain/stream"

payload = {
    "target": target,
    "top_k": 3,
    "debug": False
}

headers = {
    "Content-Type": "application/json"
}

print(f"Testing frontend API endpoint: {url}")
print(f"Target molecule: {target}")
print("Sending streaming request...")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=300, stream=True)

    if response.status_code == 200:
        print(f"Status code: {response.status_code}")
        print("Streaming response received successfully")

        # 读取所有流式数据
        full_data = []
        for line in response.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    data_str = decoded[6:].strip()
                    if data_str:
                        try:
                            data = json.loads(data_str)
                            full_data.append(data)
                            print(f"Event type: {data.get('type', 'unknown')}")
                        except:
                            pass

        print(f"\nTotal events received: {len(full_data)}")

        # 检查是否有完成事件
        complete_events = [d for d in full_data if d.get('type') == 'complete']
        if complete_events:
            print("Complete event found!")
            result = complete_events[0]
            print(f"Result keys: {list(result.keys())}")

            # 检查synthesis_route
            if 'synthesis_route' in result:
                routes = result['synthesis_route'].get('routes', [])
                print(f"Routes in synthesis_route: {len(routes)}")
                if routes:
                    first_route = routes[0]
                    print(f"First route ID: {first_route.get('route_id')}")
                    print(f"First route score: {first_route.get('total_score')}")
                    print(f"First route steps count: {len(first_route.get('steps', []))}")
        else:
            print("No complete event found")

        # 检查是否有路线事件
        route_events = [d for d in full_data if d.get('type') == 'route']
        print(f"Route events received: {len(route_events)}")

        if route_events:
            first_route_event = route_events[0].get('route', {})
            print(f"First route event route_id: {first_route_event.get('route_id')}")
            print(f"First route event steps: {len(first_route_event.get('steps', []))}")

    else:
        print(f"Failed with status code: {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"Error: {e}")
