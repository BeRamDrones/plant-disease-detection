import uvicorn
from fastapi import FastAPI, Depends
from database import Get_Status, engine
from sqlalchemy.orm import Session
from sqlalchemy import text
from models import (
    Base,
    MissionPhase,
    MissionStatus,
    SeverityLevel,
    CropClass,
    Drone,
    Flight_Mission,
    Flight_Zone,
    Parent_Model_Disease_Classification,
    Child_Models_Disease_Classification,
    Sprinkler_System
)

app = FastAPI()

# Creates all the tables in postgres
Base.metadata.create_all(bind=engine)

@app.get("/")
def Flask_Awake():
    return "Flask setup successful"

@app.get("/dbstatus")
def Check_DB_Status(db: Session = Depends(Get_Status)):
    try:
        db.execute(text("SELECT 1"))
        return "DB Active"
    except Exception as e:
        return f"Error Occured {e}"

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)