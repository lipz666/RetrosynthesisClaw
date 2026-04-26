import os
import sys

# 测试路径计算
current_dir = os.path.dirname(__file__)
print(f"当前文件目录: {current_dir}")

# 计算模型目录路径
model_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..', 'public', 'Yieldpredict', 'models'))
print(f"模型目录路径: {model_dir}")

# 检查路径是否存在
print(f"路径是否存在: {os.path.exists(model_dir)}")

if os.path.exists(model_dir):
    # 列出目录内容
    print("\n目录内容:")
    for item in os.listdir(model_dir):
        item_path = os.path.join(model_dir, item)
        print(f"  {item} (大小: {os.path.getsize(item_path)/1024/1024:.2f} MB)")

    # 检查关键文件是否存在
    required_files = [
        'residual_quantile_ydr_artifact.json',
        'residual_quantile_ydr_scaler.joblib',
        'residual_quantile_ydr_rf.joblib',
        'best_residual_quantile_ydr_vs_model.pth'
    ]
    
    print("\n检查必需文件:")
    for file in required_files:
        file_path = os.path.join(model_dir, file)
        print(f"  {file}: {'存在' if os.path.exists(file_path) else '缺失'}")

# 测试导入
print("\n测试导入...")
try:
    from retrosynthesis_claw.yield_predictor.predict_residual_quantile_ydr import ResidualQuantileYDRPredictor
    print("✓ 成功导入 ResidualQuantileYDRPredictor")
except Exception as e:
    print(f"✗ 导入失败: {e}")

# 测试模型加载
print("\n测试模型加载...")
try:
    from retrosynthesis_claw.yield_predictor.yield_predictor import get_yield_predictor
    predictor = get_yield_predictor()
    print("✓ 成功创建 YieldPredictor 实例")
    
    # 尝试加载模型
    predictor.load_predictor()
    print("✓ 成功加载模型")
except Exception as e:
    print(f"✗ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()