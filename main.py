from fastapi import Depends, FastAPI, Request
from sqlalchemy.orm import Session
from app.routers import calories, planner, water_counter, running
from app.database.db import create_tables, get_db, Water, MealPlan, RunningSession, Calories
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

app.include_router(planner.app, prefix="/mealplan", tags=["Plan"])
app.include_router(water_counter.app, prefix="/water", tags=["Water"])
app.include_router(calories.app, prefix="/calories", tags=["Calories"])
app.include_router(running.app, prefix="/running", tags=["Running"])

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("base.html", {"request": request})

@app.get("/water-page")
def read_water(request: Request, db: Session = Depends(get_db)):
    water = db.query(Water).all()
    return templates.TemplateResponse(
        "water.html",
        {"request": request, "water": water}
    )

@app.get("/running")
def read_running(request: Request, db: Session = Depends(get_db)):
    running = db.query(RunningSession).all()
    return templates.TemplateResponse(
        "running.html",
        {"request": request, "running": running}
    )

@app.get("/calories-page")
def read_calories(request: Request, db: Session = Depends(get_db)):
    calories = db.query(Calories).all()
    return templates.TemplateResponse(
        "calories.html",
        {"request": request, "calories": calories}
    )

@app.get("/mealplan")
def read_mealplan(request: Request, db: Session = Depends(get_db)):
    plans = db.query(MealPlan).all()
    return templates.TemplateResponse(
        "mealplan.html",
        {"request": request, "plan": plans}
    )

@app.on_event("startup")
def startup_event():
    create_tables()