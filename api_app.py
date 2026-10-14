"""Legacy API compatibility; never substitute constants for a trained model.

The supported browser workflow runs canonical Python locally. Native models
are managed by amr_discovery learning-* with trusted private registries.
This unconfigured API cannot return resistance or mechanism predictions.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title='AI AMR research API status', version='0.11.0')


class MICPayload(BaseModel):
    isolate_id: str
    drug: str
    mic_value: float = Field(gt=0, allow_inf_nan=False)


@app.post('/predict')
async def predict(payload: MICPayload):
    raise HTTPException(status_code=503, detail={
        'status':'RESEARCH_MODEL_NOT_CONFIGURED',
        'reason':'Use a trained session model or the controlled-learning native workflow. A single target MIC is not the reviewed other-antibiotic predictor panel.',
        'clinical_validation':False,
    })


@app.get('/status')
async def status():
    return {'status':'RESEARCH_MODEL_NOT_CONFIGURED','model_ready':False,
            'clinical_validation':False,'version':'0.11.0'}
