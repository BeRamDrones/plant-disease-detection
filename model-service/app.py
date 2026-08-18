import io
import os
import torch
from PIL import Image
from functools import lru_cache
from fastapi import FastAPI, File, UploadFile, HTTPException
from huggingface_hub import hf_hub_download

app = FastAPI(title="Project Jatayu - Model Inference Service")

# Repositories containing your 3 Parent and 34 Child models
HF_PARENT_REPO = "BeRam-Plant-Disease/Parent_Models"
HF_CHILD_REPO = "BeRam-Plant-Disease/Child-Models"
HF_TOKEN = os.getenv("HF_TOKEN")

@lru_cache(maxsize=3)
def get_model(is_parent: bool, model_name: str):
    repo_id = HF_PARENT_REPO if is_parent else HF_CHILD_REPO
    filename = f"{model_name}.pt" if not model_name.endswith('.pt') else model_name

    print(f"Fetching {filename} from Hugging Face ({repo_id})...")
    model_path = hf_hub_download(
        repo_id=repo_id, 
        filename=filename,
        token=HF_TOKEN
    )
    model = torch.hub.load('ultralytics/yolov8', 'custom', path=model_path)
    model.eval()
    return model

@app.get("/")
def health_check():
    return {"status": "Jatayu Model Inference Service is running"}

@app.post("/predict")
async def predict(is_parent: bool, model_name: str, file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))

        model = get_model(is_parent, model_name)
        results = model(image)
        predictions = results.pandas().xyxy[0].to_dict(orient="records")

        return {
            "status": "success",
            "model_used": model_name,
            "predictions": predictions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))