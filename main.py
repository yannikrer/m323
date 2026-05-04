from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
from starlette.staticfiles import StaticFiles
from pathlib import Path

from app.routers import calories, planner, water_counter, running
from app.database.db import create_tables, get_db, Water, MealPlan, RunningSession, Calories

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

jinja_env = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "app" / "templates")),
    auto_reload=True,
    cache_size=0
)

app.include_router(planner.app, prefix="/mealplan", tags=["Plan"])
app.include_router(water_counter.app, prefix="/water", tags=["Water"])
app.include_router(calories.app, prefix="/calories", tags=["Calories"])
app.include_router(running.app, prefix="/running", tags=["Running"])

@app.get("/")
def read_root(request: Request):
    template = jinja_env.get_template("base.html")
    return HTMLResponse(template.render(request=request))

@app.get("/water-page")
def read_water(request: Request, db: Session = Depends(get_db)):
    water = db.query(Water).all()
    template = jinja_env.get_template("water.html")
    return HTMLResponse(template.render(request=request, water=water))

@app.get("/running-page")
def read_running(request: Request, db: Session = Depends(get_db)):
    running_sessions = db.query(RunningSession).all()
    template = jinja_env.get_template("running.html")
    return HTMLResponse(template.render(request=request, running=running_sessions))

@app.get("/calories-page")
def read_calories(request: Request, db: Session = Depends(get_db)):
    calorie_entries = db.query(Calories).all()
    template = jinja_env.get_template("calories.html")
    return HTMLResponse(template.render(request=request, calories=calorie_entries))

@app.get("/mealplan")
def read_mealplan(request: Request, db: Session = Depends(get_db)):
    plans = db.query(MealPlan).all()
    template = jinja_env.get_template("mealplan.html")
    return HTMLResponse(template.render(request=request, plan=plans))

@app.on_event("startup")
def startup_event():
    create_tables()
