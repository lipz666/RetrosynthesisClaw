import requests
import json

# 测试完整的合成流程，包括合成思路生成
target = "BrC1=C2CCCOC2=NC=C1"
url = "http://localhost:8000/route/stream"

payload = {
    "target": target,
    "top_k": 2,
    "debug": True
}

headers = {
    "Content-Type": "application/json"
}

print(f"Testing complete synthesis flow for molecule: {target}")
print(f"API URL: {url}")
print("Sending request...")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=300, stream=True)

    if response.status_code == 200:
        print(f"Status code: {response.status_code}")
        print("Streaming response received successfully")

        # 读取所有流式数据
        full_data = []
        strategy_found = False
        route_with_strategy = False
        routes_received = 0
        
        for line in response.iter_lines():
            if line:
                try:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data_str = decoded[6:].strip()
                        if data_str:
                            try:
                                data = json.loads(data_str)
                                full_data.append(data)
                                
                                # 检查是否有strategy字段
                                if 'strategy' in data:
                                    strategy_found = True
                                    print("\n--- Synthesis Strategy Found ---")
                                    print(f"Strategy content: {data['strategy']['strategy'][:300]}...")
                                    print(f"Strategy length: {len(data['strategy']['strategy'])} characters")
                                
                                # 检查是否有route事件，查看route中的synthesis_strategy
                                if data.get('type') == 'route' and 'route' in data:
                                    route = data['route']
                                    routes_received += 1
                                    if 'metadata' in route and 'synthesis_strategy' in route['metadata']:
                                        strategy = route['metadata']['synthesis_strategy']
                                        if strategy:
                                            route_with_strategy = True
                                            print(f"\n--- Route {routes_received} Synthesis Strategy ---")
                                            print(f"Strategy content: {strategy[:300]}...")
                                            print(f"Strategy length: {len(strategy)} characters")
                            except Exception as e:
                                print(f"Error parsing JSON: {e}")
                except Exception as e:
                    print(f"Error decoding line: {e}")

        print(f"\nTotal events received: {len(full_data)}")
        print(f"Total routes received: {routes_received}")
        
        # 检查最后一个complete事件
        complete_events = [d for d in full_data if d.get('type') == 'complete']
        if complete_events:
            complete_event = complete_events[-1]
            if 'routes' in complete_event:
                routes = complete_event['routes']
                print(f"\nComplete event routes: {len(routes)}")
                if routes:
                    for i, route in enumerate(routes):
                        if 'metadata' in route and 'synthesis_strategy' in route['metadata']:
                            strategy = route['metadata']['synthesis_strategy']
                            if strategy:
                                route_with_strategy = True
                                print(f"\n--- Complete Event Route {i+1} Strategy ---")
                                print(f"Strategy content: {strategy[:300]}...")
                                print(f"Strategy length: {len(strategy)} characters")

        if strategy_found or route_with_strategy:
            print("\n✅ SUCCESS: Synthesis strategy generation is working!")
        else:
            print("\n❌ FAILED: No synthesis strategy found")

    else:
        print(f"Failed with status code: {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"Error: {e}")
