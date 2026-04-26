import os
from typing import Dict, Any, List

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from predict_residual_quantile_ydr import ResidualQuantileYDRPredictor


DEFAULT_MODEL_DIR = r'C:\Users\lpz\Desktop\Yiled Models\E\ResidualQuantileYDR_VirtualScreening_RandomBaseline\models'


class PredictRequest(BaseModel):
    samples: List[Dict[str, Any]] = Field(..., description='每个样本是一条记录，键名需包含训练用特征列')


class PredictResponse(BaseModel):
    n_samples: int
    predictions: List[Dict[str, Any]]


class PredictSmilesRequest(BaseModel):
    samples: List[Dict[str, Any]] = Field(
        ...,
        description='每个样本需包含 reactant_smiles 和 product_smiles'
    )


class PredictSmilesResponse(BaseModel):
    n_samples: int
    predictions: List[Dict[str, Any]]

app = FastAPI(title='Residual Quantile YDR Inference API', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

_predictor = None


def get_predictor() -> ResidualQuantileYDRPredictor:
    global _predictor
    if _predictor is None:
        model_dir = os.getenv('RQYDR_MODEL_DIR', DEFAULT_MODEL_DIR)
        _predictor = ResidualQuantileYDRPredictor(model_dir=model_dir)
    return _predictor


@app.get('/health')
def health_check():
    return {'status': 'ok'}


@app.post('/predict', response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        if not req.samples:
            raise HTTPException(status_code=400, detail='samples 不能为空')

        df = pd.DataFrame(req.samples)
        predictor = get_predictor()
        out_df = predictor.predict_dataframe(df)

        keep_cols = list(df.columns) + ['rf_baseline_pred', 'predicted_yield']
        keep_cols = [c for c in keep_cols if c in out_df.columns]

        return PredictResponse(
            n_samples=len(out_df),
            predictions=out_df[keep_cols].to_dict(orient='records')
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'预测失败: {str(e)}')


@app.post('/predict_smiles', response_model=PredictSmilesResponse)
def predict_smiles(req: PredictSmilesRequest):
    try:
        if not req.samples:
            raise HTTPException(status_code=400, detail='samples 不能为空')

        df = pd.DataFrame(req.samples)
        if 'reactant_smiles' not in df.columns or 'product_smiles' not in df.columns:
            raise HTTPException(status_code=400, detail='每条样本必须包含 reactant_smiles 和 product_smiles')

        predictor = get_predictor()
        out_df = predictor.predict_smiles_dataframe(
            df,
            reactant_col='reactant_smiles',
            product_col='product_smiles'
        )

        return PredictSmilesResponse(
            n_samples=len(out_df),
            predictions=out_df.to_dict(orient='records')
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'SMILES预测失败: {str(e)}')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('api_residual_quantile_ydr:app', host='0.0.0.0', port=8000, reload=False)
