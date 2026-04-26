import requests
import json

# 测试服务器返回的数据格式
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

print(f"Testing server response format for molecule: {target}")
print(f"API URL: {url}")
print("Sending request...")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=300, stream=True)

    if response.status_code == 200:
        print(f"Status code: {response.status_code}")
        print("Streaming response received successfully")

        # 读取所有流式数据
        full_data = []
        event_count = 0
        
        for line in response.iter_lines():
            if line:
                try:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data_str = decoded[6:].strip()
                        if data_str:
                            event_count += 1
                            print(f"\nEvent {event_count}:")
                            print(f"Raw data: {data_str[:500]}...")
                            
                            # 检查是否包含 'class' 关键字
                            if 'class' in data_str:
                                print("⚠️  Found 'class' keyword in response!")
                                # 找出包含 'class' 的位置
                                class_positions = []
                                pos = data_str.find('class')
                                while pos != -1:
                                    class_positions.append(pos)
                                    pos = data_str.find('class', pos + 5)
                                print(f"Class positions: {class_positions}")
                                # 打印包含 'class' 的上下文
                                for pos in class_positions:
                                    start = max(0, pos - 20)
                                    end = min(len(data_str), pos + 20)
                                    print(f"Context: ...{data_str[start:end]}...")
                            
                            try:
                                data = json.loads(data_str)
                                full_data.append(data)
                                print("✅ JSON parsed successfully")
                            except Exception as e:
                                print(f"❌ JSON parse error: {e}")
                except Exception as e:
                    print(f"Error decoding line: {e}")

        print(f"\nTotal events received: {event_count}")
        print(f"Total valid JSON events: {len(full_data)}")

    else:
        print(f"Failed with status code: {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"Error: {e}")
