import json
from typing import Dict, Any

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from app.database.db import MealPlan, get_db
from app.schemas.planner import MealPlanRequest, MealPlanResponse, MealPlanListItem

app = APIRouter()

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


# ============== Pure Functions ==============

def calculate_bmi(weight: float, height_cm: float) -> float:
    return round(weight / ((height_cm / 100) ** 2), 1)


def format_foods(foods: list[str]) -> str:
    return ", ".join(foods)


def build_prompt(data: MealPlanRequest) -> str:
    bmi = calculate_bmi(data.weight, data.height)
    foods = format_foods(data.favorite_foods)

    return f"""Du bist ein professioneller Ernährungsberater.
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

WICHTIG: Formatiere die Antwort als sauberes Markdown mit:
- ## Tag 1, ## Tag 2 etc. als Überschriften
- ### Frühstück, ### Mittagessen etc. als Unterüberschriften
- Jede Mahlzeit mit: Beschreibung, Kalorien und Makros
- Am Ende eine ## Zusammenfassung mit Gesamtübersicht

Erstelle jetzt den vollständigen {data.days}-Tage Ernährungsplan:""".strip()


def create_meal_plan_dict(data: MealPlanRequest, plan_text: str) -> Dict[str, Any]:
    return {
        "age": data.age,
        "height": data.height,
        "weight": data.weight,
        "eating_habit": data.eating_habit,
        "favorite_foods": json.dumps(data.favorite_foods),
        "goal": data.goal,
        "days": data.days,
        "plan": plan_text
    }


def create_response(data: MealPlanRequest, plan_text: str, date) -> MealPlanResponse:
    return MealPlanResponse(
        request=data,
        plan=plan_text,
        date=date
    )


# ============== Ollama Communication ==============

async def fetch_ollama_response(client: httpx.AsyncClient, prompt: str) -> str:
    response = await client.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    })
    response.raise_for_status()
    return response.json().get("response", "").strip()


def handle_ollama_error(error: Exception) -> HTTPException:
    error_handlers = {
        httpx.ConnectError: HTTPException(
            status_code=503,
            detail="Ollama läuft nicht! Starte Ollama mit: ollama serve"
        ),
        httpx.TimeoutException: HTTPException(
            status_code=504,
            detail="Ollama Timeout - Modell braucht zu lange"
        )
    }

    return error_handlers.get(type(error), HTTPException(
        status_code=500,
        detail=f"Fehler: {str(error)}"
    ))


# ============== Database Service Functions ==============

def save_meal_plan(db: Session, data: MealPlanRequest, plan_text: str) -> MealPlan:
    plan_dict = create_meal_plan_dict(data, plan_text)
    db_entry = MealPlan(**plan_dict)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


def get_all_plans_from_db(db: Session) -> list[MealPlan]:
    return db.query(MealPlan).order_by(MealPlan.date.desc()).all()


def get_plan_by_id(db: Session, plan_id: int) -> MealPlan | None:
    return db.query(MealPlan).filter(MealPlan.id == plan_id).first()


def delete_plan_by_id(db: Session, plan_id: int) -> bool:
    plan = get_plan_by_id(db, plan_id)
    if plan:
        db.delete(plan)
        db.commit()
        return True
    return False


# ============== Route Handlers ==============

@app.post("/generate", response_model=MealPlanResponse)
async def create_meal_plan(data: MealPlanRequest, db: Session = Depends(get_db)):
    prompt = build_prompt(data)

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            plan_text = await fetch_ollama_response(client, prompt)
    except Exception as e:
        raise handle_ollama_error(e)

    db_entry = save_meal_plan(db, data, plan_text)
    return create_response(data, plan_text, db_entry.date)


@app.post("/generate/stream")
async def stream_meal_plan(data: MealPlanRequest, db: Session = Depends(get_db)):
    prompt = build_prompt(data)
    full_text = ""

    async def generate():
        nonlocal full_text
        try:
            async with httpx.AsyncClient(timeout=350.0) as client:
                async with client.stream("POST", OLLAMA_URL, json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": True
                }) as response:
                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            full_text += token
                            yield json.dumps({"token": token, "done": False}) + "\n"
                            if chunk.get("done"):
                                save_meal_plan(db, data, full_text)
                                yield json.dumps({"token": "", "done": True, "saved": True}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e), "done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.get("/", response_model=list[MealPlanListItem])
def get_all_plans(db: Session = Depends(get_db)):
    plans = get_all_plans_from_db(db)
    return [MealPlanListItem(
        id=p.id,
        date=p.date,
        age=p.age,
        eating_habit=p.eating_habit,
        goal=p.goal,
        days=p.days
    ) for p in plans]


@app.get("/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan nicht gefunden")
    return plan


@app.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    if not delete_plan_by_id(db, plan_id):
        raise HTTPException(status_code=404, detail="Plan nicht gefunden")
    return {"message": "Plan gelöscht"}
