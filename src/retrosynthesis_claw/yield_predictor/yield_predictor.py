"""产率预测模块集成"""

from __future__ import annotations

import os
from typing import Dict, Any, List, Optional

import pandas as pd
from fastapi import HTTPException

from .predict_residual_quantile_ydr import ResidualQuantileYDRPredictor


class YieldPredictor:
    """产率预测器包装类"""
    
    def __init__(self, model_dir: str):
        """初始化产率预测器
        
        Args:
            model_dir: 模型目录路径
        """
        self.model_dir = model_dir
        self.predictor: Optional[ResidualQuantileYDRPredictor] = None
    
    def load_predictor(self) -> ResidualQuantileYDRPredictor:
        """加载预测器实例
        
        Returns:
            ResidualQuantileYDRPredictor 实例
        
        Raises:
            Exception: 模型加载失败
        """
        if self.predictor is None:
            try:
                self.predictor = ResidualQuantileYDRPredictor(model_dir=self.model_dir)
            except Exception as e:
                raise Exception(f"模型加载失败: {str(e)}")
        return self.predictor
    
    def validate_smiles(self, smiles: str) -> bool:
        """验证SMILES格式是否有效
        
        Args:
            smiles: SMILES字符串
            
        Returns:
            bool: SMILES是否有效
        """
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        return mol is not None
    
    def predict_yield(self, reactant_smiles: str, product_smiles: str) -> Dict[str, Any]:
        """预测反应产率
        
        Args:
            reactant_smiles: 反应物SMILES (单个分子或两个分子用点分隔)
            product_smiles: 产物SMILES
            
        Returns:
            Dict: 包含预测结果的字典
            
        Raises:
            ValueError: 无效的SMILES格式
            Exception: 预测失败
        """
        # 验证SMILES格式
        if not self.validate_smiles(product_smiles):
            raise ValueError(f"无效的产物SMILES: {product_smiles}")
        
        # 验证反应物SMILES
        # 处理两个反应物的情况
        if '.' in reactant_smiles:
            reactants = reactant_smiles.split('.')
            if len(reactants) != 2:
                raise ValueError(f"反应物SMILES格式错误，应为 'smiles1.smiles2': {reactant_smiles}")
            for reactant in reactants:
                if not self.validate_smiles(reactant):
                    raise ValueError(f"无效的反应物SMILES: {reactant}")
        else:
            if not self.validate_smiles(reactant_smiles):
                raise ValueError(f"无效的反应物SMILES: {reactant_smiles}")
        
        try:
            predictor = self.load_predictor()
            
            # 创建输入DataFrame
            df = pd.DataFrame({
                'reactant_smiles': [reactant_smiles],
                'product_smiles': [product_smiles]
            })
            
            # 执行预测
            result_df = predictor.predict_smiles_dataframe(df)
            
            # 转换为字典格式
            result = result_df.iloc[0].to_dict()
            
            # 标准化输出
            return {
                'reactant_smiles': result.get('reactant_smiles'),
                'product_smiles': result.get('product_smiles'),
                'predicted_yield': float(result.get('predicted_yield', 0.0)),
                'rf_baseline_pred': float(result.get('rf_baseline_pred', 0.0)),
                'status': 'success'
            }
            
        except ValueError as e:
            raise e
        except Exception as e:
            raise Exception(f"预测失败: {str(e)}")
    
    def predict_batch(self, samples: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """批量预测产率
        
        Args:
            samples: 样本列表，每个样本包含 'reactant_smiles' 和 'product_smiles'
            
        Returns:
            List[Dict]: 预测结果列表
        """
        results = []
        for sample in samples:
            try:
                result = self.predict_yield(
                    sample.get('reactant_smiles', ''),
                    sample.get('product_smiles', '')
                )
            except Exception as e:
                result = {
                    'reactant_smiles': sample.get('reactant_smiles', ''),
                    'product_smiles': sample.get('product_smiles', ''),
                    'error': str(e),
                    'status': 'error'
                }
            results.append(result)
        return results


# 全局预测器实例
_yield_predictor: Optional[YieldPredictor] = None


def get_yield_predictor() -> YieldPredictor:
    """获取产率预测器实例
    
    Returns:
        YieldPredictor 实例
    """
    global _yield_predictor
    if _yield_predictor is None:
        # 使用环境变量或默认路径
        model_dir = os.getenv(
            'YIELD_PREDICTOR_MODEL_DIR',
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'public', 'Yieldpredict', 'models'))
        )
        # 打印路径用于调试
        print(f"Model directory: {model_dir}")
        _yield_predictor = YieldPredictor(model_dir=model_dir)
    return _yield_predictor


def predict_yield(reactant_smiles: str, product_smiles: str) -> Dict[str, Any]:
    """便捷函数：预测产率
    
    Args:
        reactant_smiles: 反应物SMILES
        product_smiles: 产物SMILES
        
    Returns:
        Dict: 预测结果
    """
    predictor = get_yield_predictor()
    return predictor.predict_yield(reactant_smiles, product_smiles)


def predict_yield_batch(samples: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """便捷函数：批量预测产率
    
    Args:
        samples: 样本列表
        
    Returns:
        List[Dict]: 预测结果列表
    """
    predictor = get_yield_predictor()
    return predictor.predict_batch(samples)