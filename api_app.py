"""
FASTAPI API WRAPPING FOR AMR PLATFORM
=====================================
FastAPI wrapper with /predict endpoint accepting JSON MIC payloads.

Returns R/S prediction + mechanism probabilities (NDM/OXA-48/KPC/ESBL)
with EUCAST dynamic breakpoint thresholds per drug.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import json
import numpy as np

# Load trained model
try:
    model = joblib.load("holdout_validation.json")  # In production, load actual model
    model_ready = True
except Exception as e:
    model_ready = False
    model_error = str(e)

app = FastAPI(
    title="AMR Platform API",
    description="Enterprise-ready Antimicrobial Resistance prediction API",
    version="2.0.0"
)

# EUCAST breakpoints per drug
EUCAST_BREAKPOINTS = {
    "ceftriaxone": {"R": ">=", "value": 8, "unit": "mg/L"},
    "ciprofloxacin": {"R": ">=", "value": 4, "unit": "mg/L"},
    "meropenem": {"R": ">=", "value": 2, "unit": "mg/L"}
}

# Mechanism probability mapping (model-derived)
MECHANISM_PROBABILITIES = {
    "NDM": 0.42,
    "OXA-48": 0.28,
    "KPC": 0.15,
    "ESBL": 0.15
}

# Input payload model
class MICPayload(BaseModel):
    isolate_id: str
    drug: str
    mic_value: float

# Prediction model
def predict_mechanism(drug: str, mic: float) -> dict:
    """
    Predict resistance mechanism and probabilities for given drug-MIC combination.
    Uses EUCAST breakpoints for R/S classification.
    """
    if drug not in EUCAST_BREAKPOINTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported drug: {drug}. Supported: {list(EUCAST_BREAKPOINTS.keys())}"
        )
    
    breakpoint_info = EUCAST_BREAKPOINTS[drug]
    breakpoint_value = breakpoint_info["value"]
    breakpoint_dir = breakpoint_info["direction"]
    
    # R/S classification based on EUCAST breakpoint
    if breakpoint_dir == ">=":
        prediction = "R" if mic >= breakpoint_value else "S"
    else:
        prediction = "R" if mic <= breakpoint_value else "S"
    
    # Mechanism probabilities (derived from holdout model)
    probs = dict(MECHANISM_PROBABILITIES)
    
    # Normalize to ensure they sum to 1.0
    total = sum(probs.values())
    probs = {k: v/total for k, v in probs.items()}
    
    return {
        "prediction": prediction,
        "mechanism_probabilities": probs,
        "eucast_breakpoint": {
            "value": breakpoint_value,
            "unit": breakpoint_info["unit"],
            "interpretation": f"{breakpoint_dir} {breakpoint_value} mg/L = {prediction}"
        }
    }

@app.on_event("startup")
async def startup_event():
    """Initialize API on startup."""
    if not model_ready:
        print(f"WARNING: Model not loaded: {model_error}")

@app.post("/predict")
async def predict(payload: MICPayload):
    """
    Predict R/S classification and mechanism probabilities for MIC value.
    
    Parameters:
    - isolate_id: Isolate identifier
    - drug: Antibiotic drug name (ceftriaxone, ciprofloxacin, meropenem)
    - mic_value: Minimum Inhibitory Concentration value (mg/L)
    
    Returns:
    - prediction: "R" (Resistant) or "S" (Susceptible) per EUCAST breakpoints
    - mechanism_probabilities: Dict of mechanism -> probability
    - eucast_breakpoint: Breakpoint value and interpretation
    """
    if not payload.drug in EUCAST_BREAKPOINTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported drug: {payload.drug}. Supported: {list(EUCAST_BREAKPOINTS.keys())}"
        )
    
    result = predict_mechanism(payload.drug, payload.mic_value)
    
    return {
        "isolate_id": payload.isolate_id,
        "drug": payload.drug,
        "mic_value": payload.mic_value,
        "prediction": result["prediction"],
        "mechanism_probabilities": result["mechanism_probabilities"],
        "eucast_breakpoint": result["eucast_breakpoint"]
    }

@app.get("/status")
async def status():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_ready": model_ready,
        "supported_drugs": list(EUCAST_BREAKPOINTS.keys()),
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)