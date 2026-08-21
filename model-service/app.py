import io
import os
import gc
from PIL import Image
from functools import lru_cache
from fastapi import FastAPI, File, UploadFile, HTTPException
from huggingface_hub import hf_hub_download

# Import your PureONNX engine. 
# Adjust this path if your engine file is located elsewhere in your directory.
from app.services.onnx_engine import PureONNX

app = FastAPI(title="Project Jatayu - Model Inference Service")

# Repositories containing your 3 Parent and 34 Child INT8 ONNX models
HF_PARENT_REPO = "BeRam-Plant-Disease/Parent_Models"
HF_CHILD_REPO = "BeRam-Plant-Disease/Child-Models"
HF_TOKEN = os.getenv("HF_TOKEN")

@lru_cache(maxsize=1)  # CRITICAL: Changed from 3 to 1 to fit inside Render's 512MB RAM limit
def get_model(is_parent: bool, model_name: str):
    # Force Python to clear previous model memory before loading a new one
    gc.collect()
    
    repo_id = HF_PARENT_REPO if is_parent else HF_CHILD_REPO
    
    # Ensure incoming requests map to the optimized ONNX format, not .pt
    base_name = model_name.replace('.pt', '').replace('_int8.onnx', '')
    filename = f"{base_name}_int8.onnx"

    print(f"Fetching {filename} from Hugging Face ({repo_id})...")
    model_path = hf_hub_download(
        repo_id=repo_id, 
        filename=filename,
        token=HF_TOKEN
    )
    
    # Initialize your custom ONNX engine instead of torch.hub
    model = PureONNX(model_path)
    return model

@app.get("/")
def health_check():
    return {"status": "Jatayu Model Inference Service is running in ONNX Mode"}

@app.post("/predict")
async def predict(is_parent: bool, model_name: str, file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))

        # Lazy load the ONNX model (drops the old one automatically)
        model = get_model(is_parent, model_name)
        
        # Run inference using your PureONNX class
        # (Note: PyTorch's results.pandas().xyxy[0] is no longer needed here)
        results = model.predict(image) 

        return {
            "status": "success",
            "model_used": f"{model_name}_int8.onnx",
            "predictions": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))