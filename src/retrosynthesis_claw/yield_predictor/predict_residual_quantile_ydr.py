import os
import json
import argparse
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.nn import BatchNorm1d, Dropout, Linear, LeakyReLU

from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem


class BaseMLP(nn.Module):
    def __init__(self, input_dim, hidden_dims, dropout_rate=0.2, use_batch_norm=True):
        super().__init__()
        layers = []
        prev_dim = input_dim
        for dim in hidden_dims:
            layers.append(Linear(prev_dim, dim))
            if use_batch_norm:
                layers.append(BatchNorm1d(dim))
            layers.append(LeakyReLU(0.1))
            layers.append(Dropout(dropout_rate))
            prev_dim = dim
        self.backbone = nn.Sequential(*layers)
        self.embedding_dim = prev_dim

    def forward(self, x):
        return self.backbone(x)


class ResidualQuantileYDRModel(BaseMLP):
    def __init__(self, input_dim, hidden_dims, dropout_rate, quantiles):
        super().__init__(input_dim, hidden_dims, dropout_rate)
        self.quantiles = quantiles
        self.quantile_head = Linear(self.embedding_dim, len(self.quantiles))

    def forward(self, x):
        return self.quantile_head(super().forward(x))

    def predict_yield(self, x, rf_pred, y_min=0.0, y_max=100.0):
        q_res = self.forward(x)
        q50_idx = self.quantiles.index(0.5)
        q50_res = q_res[:, q50_idx]
        pred = rf_pred + q50_res
        return torch.clamp(pred, y_min, y_max)


class ResidualQuantileYDRPredictor:
    def __init__(
        self,
        model_dir,
        device=None,
        morgan_radius=2,
        morgan_nbits=1024,
        use_chirality=False
    ):
        self.model_dir = model_dir
        self.device = torch.device(device if device else ('cuda' if torch.cuda.is_available() else 'cpu'))
        self.morgan_radius = int(morgan_radius)
        self.morgan_nbits = int(morgan_nbits)
        self.use_chirality = bool(use_chirality)

        artifact_path = os.path.join(model_dir, 'residual_quantile_ydr_artifact.json')
        scaler_path = os.path.join(model_dir, 'residual_quantile_ydr_scaler.joblib')
        rf_path = os.path.join(model_dir, 'residual_quantile_ydr_rf.joblib')

        if not os.path.exists(artifact_path):
            raise FileNotFoundError(f'找不到工件文件: {artifact_path}')
        if not os.path.exists(scaler_path):
            raise FileNotFoundError(f'找不到 scaler 文件: {scaler_path}')
        if not os.path.exists(rf_path):
            raise FileNotFoundError(f'找不到 RF 文件: {rf_path}')

        with open(artifact_path, 'r', encoding='utf-8') as f:
            self.artifact = json.load(f)

        self.feature_cols = self.artifact['feature_cols']
        self.quantiles = self.artifact['fusion_quantiles']
        self.yield_range = self.artifact.get('yield_range', [0.0, 100.0])

        # 自动从训练特征列推断指纹长度，避免与部署时参数不一致
        reactant_fp_cols = [c for c in self.feature_cols if c.startswith('reactant_fp_')]
        product_fp_cols = [c for c in self.feature_cols if c.startswith('product_fp_')]
        if reactant_fp_cols and product_fp_cols:
            self.morgan_nbits = max(len(reactant_fp_cols), len(product_fp_cols))

        self.scaler = joblib.load(scaler_path)
        self.rf_model = joblib.load(rf_path)

        input_dim = len(self.feature_cols) + 1
        self.model = ResidualQuantileYDRModel(
            input_dim=input_dim,
            hidden_dims=self.artifact['hidden_dims'],
            dropout_rate=self.artifact['dropout_rate'],
            quantiles=self.quantiles
        ).to(self.device)

        checkpoint_path = self.artifact['model_checkpoint']
        if not os.path.isabs(checkpoint_path):
            checkpoint_path = os.path.join(model_dir, checkpoint_path)
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()

    def _prepare_features(self, df):
        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f'输入缺少特征列，缺失数量={len(missing)}，示例: {missing[:10]}')

        X_raw = df[self.feature_cols].astype(np.float32).values
        X_scaled = self.scaler.transform(X_raw)
        rf_pred = self.rf_model.predict(X_scaled).astype(np.float32)
        X_fusion = np.concatenate([X_scaled, rf_pred.reshape(-1, 1)], axis=1).astype(np.float32)
        return X_fusion, rf_pred

    def predict_dataframe(self, df):
        X_fusion, rf_pred = self._prepare_features(df)
        X_tensor = torch.from_numpy(X_fusion).to(self.device)
        rf_tensor = torch.from_numpy(rf_pred).to(self.device)

        with torch.no_grad():
            y_pred = self.model.predict_yield(
                X_tensor,
                rf_tensor,
                y_min=float(self.yield_range[0]),
                y_max=float(self.yield_range[1])
            ).cpu().numpy()

        out = df.copy()
        out['rf_baseline_pred'] = rf_pred
        out['predicted_yield'] = y_pred
        return out

    def _smiles_to_morgan_array(self, smiles: str) -> np.ndarray:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f'无效SMILES: {smiles}')

        bitvect = AllChem.GetMorganFingerprintAsBitVect(
            mol,
            radius=self.morgan_radius,
            nBits=self.morgan_nbits,
            useChirality=self.use_chirality
        )
        arr = np.zeros((self.morgan_nbits,), dtype=np.float32)
        DataStructs.ConvertToNumpyArray(bitvect, arr)
        return arr

    def smiles_to_feature_row(self, reactant_smiles: str, product_smiles: str) -> dict:
        reactant_fp = self._smiles_to_morgan_array(reactant_smiles)
        product_fp = self._smiles_to_morgan_array(product_smiles)

        row = {}
        for i in range(self.morgan_nbits):
            row[f'reactant_fp_{i}'] = float(reactant_fp[i])
        for i in range(self.morgan_nbits):
            row[f'product_fp_{i}'] = float(product_fp[i])
        return row

    def predict_smiles_dataframe(
        self,
        smiles_df: pd.DataFrame,
        reactant_col='reactant_smiles',
        product_col='product_smiles'
    ) -> pd.DataFrame:
        if reactant_col not in smiles_df.columns or product_col not in smiles_df.columns:
            raise ValueError(f'输入必须包含列: {reactant_col}, {product_col}')

        rows = []
        for _, r in smiles_df.iterrows():
            reactant_smiles = str(r[reactant_col]).strip()
            product_smiles = str(r[product_col]).strip()
            feat_row = self.smiles_to_feature_row(reactant_smiles, product_smiles)
            feat_row[reactant_col] = reactant_smiles
            feat_row[product_col] = product_smiles
            rows.append(feat_row)

        feat_df = pd.DataFrame(rows)
        pred_df = self.predict_dataframe(feat_df)

        keep_cols = [reactant_col, product_col, 'rf_baseline_pred', 'predicted_yield']
        keep_cols = [c for c in keep_cols if c in pred_df.columns]
        return pred_df[keep_cols]


def main():
    parser = argparse.ArgumentParser(description='Residual Quantile YDR 离线预测脚本')
    parser.add_argument('--input_csv', required=True, help='待预测CSV路径')
    parser.add_argument('--output_csv', required=True, help='预测结果CSV保存路径')
    parser.add_argument('--model_dir', required=True, help='模型目录（包含artifact/scaler/rf/checkpoint）')
    parser.add_argument('--device', default=None, help='cpu 或 cuda；默认自动选择')
    args = parser.parse_args()

    df = pd.read_csv(args.input_csv)
    predictor = ResidualQuantileYDRPredictor(model_dir=args.model_dir, device=args.device)
    pred_df = predictor.predict_dataframe(df)

    os.makedirs(os.path.dirname(args.output_csv) or '.', exist_ok=True)
    pred_df.to_csv(args.output_csv, index=False)

    print('预测完成')
    print(f'输入文件: {args.input_csv}')
    print(f'输出文件: {args.output_csv}')
    print(f'样本数: {len(pred_df)}')


if __name__ == '__main__':
    main()
