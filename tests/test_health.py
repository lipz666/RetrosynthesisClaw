import requests

# 测试健康状态端点
url = "http://localhost:8000/health"

print(f"测试健康状态端点: {url}")
print("正在发送请求...")

try:
    response = requests.get(url, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        print("\n✅ 健康状态检查成功！")
        print(f"状态码: {response.status_code}")
        print(f"返回结果: {result}")
    else:
        print(f"\n❌ 健康状态检查失败")
        print(f"状态码: {response.status_code}")
        print(f"错误信息: {response.text}")
        
except Exception as e:
    print(f"\n❌ 请求失败: {e}")
