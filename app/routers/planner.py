import json

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from app.database.db import MealPlan, get_db
from app.schemas.planner import MealPlanRequest, MealPlanResponse

app = APIRouter()

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

def build_prompt(data: MealPlanRequest) -> str:
    foods = ", ".join(data.favorite_foods)

    bmi = round(data.weight / ((data.height / 100) ** 2), 1)

    return f"""
    Du bist ein professioneller Ernährungsberater.
    Erstelle einen detaillierten Ernährungsplan für folgende Person:

    Personendaten:
    - Alter:        {data.age} Jahre
    - Größe:        {data.height} cm
    - Gewicht:      {data.weight} kg
    - BMI:          {bmi}
    - Ziel:         {data.goal}
    - Essverhalten: {data.eating_habit}
    - Lieblingsessen: {foods}

    Anforderungen:
    - Erstelle einen {data.days}-Tage Ernährungsplan
    - Jeder Tag soll Frühstück, Mittagessen, Abendessen und 1-2 Snacks enthalten
    - Berücksichtige das Essverhalten ({data.eating_habit})
    - Baue die Lieblingsessen ({foods}) sinnvoll ein
    - Gib für jede Mahlzeit ungefähre Kalorien und Makros (Protein, Kohlenhydrate, Fett) an
    - Passe den Plan dem Ziel "{data.goal}" an
    - Schreibe auf Deutsch
    - Formatiere den Plan übersichtlich mit Emojis

    Erstelle jetzt den vollständigen {data.days}-Tage Ernährungsplan:
    """.strip()

@app.post("/", response_model=MealPlanResponse)
async def create_meal_plan(data: MealPlanRequest, db: Session = Depends(get_db)):

    prompt = build_prompt(data)

    try: 
        async with httpx.AsyncClient(timeout=120.0) as client: 
            response = await client.post(OLLAMA_URL, json = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            })
            response.raise_for_status()
            result = response.json()
            plan_text = result.get("response", "").strip()

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Ollama läuft nciht! Starte Ollama mit: ollama serve"
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Ollama Timeout - Modell braucht zu lange"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"X Fehler: {str(e)}")
    
    db_entry = MealPlan(
        age            = data.age,
        height         = data.height,
        weight         = data.weight,
        eating_habit   = data.eating_habit,
        favorite_foods = json.dumps(data.favorite_foods),
        goal           = data.goal,
        days           = data.days,
        plan           = plan_text
    )    

    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    return MealPlanResponse(
        request = data,
        plan    = plan_text,
        date    = db_entry.date
    )

@app.post("/stream")
async def stream_meal_plan(data: MealPlanRequest):
    prompt = build_prompt(data)

    async def generate():
        try:
            async with httpx.AsyncClient(timeout=350.0) as client:
                async with client.stream("POST", OLLAMA_URL, json={
                    "model":  OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": True
                }) as response:
                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            yield token
                            if chunk.get("done"):
                                break
        except Exception as e:
            yield f"\n❌ Fehler: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")

@app.get("/")
def get_all_plans(db: Session = Depends(get_db)):
    plans = db.query(MealPlan).order_by(MealPlan.date.desc()).all()
    return plans

@app.get("/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(MealPlan).filter(MealPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan nicht gefunden")
    return plan

@app.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(MealPlan).filter(MealPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan nicht gefunden")
    db.delete(plan)
    db.commit()
    return {"message": "Plan gelöscht"}