from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date, timedelta
from typing import List, Optional

from app.database.db import Calories, get_db
from app.schemas.calories import (
    CalorieEntryCreate,
    CalorieEntryUpdate,
    CalorieEntryResponse,
    DailySummary,
    WeeklySummary,
    MealSummary,
    MacroPercentages,
    NutritionGoals,
    DailyProgress
)

app = APIRouter()

MEAL_TYPES = ["Frühstück", "Mittagessen", "Abendessen", "Snack"]

def validate_meal_type(meal: str):
    if meal not in MEAL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger Mahlzeittyp. Erlaubt: {', '.join(MEAL_TYPES)}"
        )

def calculate_macro_percentages(protein: float, carbs: float, fat: float) -> MacroPercentages:
    protein_cal = protein * 4
    carbs_cal = carbs * 4
    fat_cal = fat * 9
    total_cal = protein_cal + carbs_cal + fat_cal
    
    if total_cal == 0:
        return MacroPercentages(
            protein_percent=0, carbs_percent=0, fat_percent=0,
            protein_grams=protein, carbs_grams=carbs, fat_grams=fat
        )
    
    return MacroPercentages(
        protein_percent=round((protein_cal / total_cal) * 100, 1),
        carbs_percent=round((carbs_cal / total_cal) * 100, 1),
        fat_percent=round((fat_cal / total_cal) * 100, 1),
        protein_grams=protein,
        carbs_grams=carbs,
        fat_grams=fat
    )

@app.post("/", response_model=CalorieEntryResponse, status_code=201)
def create_calorie_entry(entry: CalorieEntryCreate, db: Session = Depends(get_db)):
    validate_meal_type(entry.meal)
    
    db_entry = Calories(
        date=entry.date,
        meal=entry.meal,
        food=entry.food,
        amount=entry.amount,
        calories=entry.calories,
        protein=entry.protein,
        carbs=entry.carbs,
        fat=entry.fat,
        note=entry.note
    )
    
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    
    return db_entry

@app.get("/", response_model=List[CalorieEntryResponse])
def get_all_entries(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    entries = db.query(Calories).order_by(Calories.date.desc(), Calories.id.desc()).offset(skip).limit(limit).all()
    return entries

@app.get("/today", response_model=DailySummary)
def get_today_entries(db: Session = Depends(get_db)):
    today = date.today()
    entries = db.query(Calories).filter(Calories.date == today).all()
    
    total_calories = sum(e.calories for e in entries)
    total_protein = sum(e.protein for e in entries)
    total_carbs = sum(e.carbs for e in entries)
    total_fat = sum(e.fat for e in entries)
    
    return DailySummary(
        date=today,
        total_calories=round(total_calories, 1),
        total_protein=round(total_protein, 1),
        total_carbs=round(total_carbs, 1),
        total_fat=round(total_fat, 1),
        meal_count=len(entries),
        meals=entries
    )

@app.get("/date/{target_date}", response_model=DailySummary)
def get_entries_by_date(target_date: date, db: Session = Depends(get_db)):
    entries = db.query(Calories).filter(Calories.date == target_date).all()
    
    total_calories = sum(e.calories for e in entries)
    total_protein = sum(e.protein for e in entries)
    total_carbs = sum(e.carbs for e in entries)
    total_fat = sum(e.fat for e in entries)
    
    return DailySummary(
        date=target_date,
        total_calories=round(total_calories, 1),
        total_protein=round(total_protein, 1),
        total_carbs=round(total_carbs, 1),
        total_fat=round(total_fat, 1),
        meal_count=len(entries),
        meals=entries
    )

@app.get("/week", response_model=WeeklySummary)
def get_week_summary(
    start_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if start_date is None:
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
    else:
        end_date = start_date + timedelta(days=6)
    
    entries = db.query(Calories).filter(
        and_(Calories.date >= start_date, Calories.date <= end_date)
    ).all()
    
    daily_data = {}
    for entry in entries:
        if entry.date not in daily_data:
            daily_data[entry.date] = []
        daily_data[entry.date].append(entry)
    
    daily_summaries = []
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    
    current_date = start_date
    while current_date <= end_date:
        day_entries = daily_data.get(current_date, [])
        day_calories = sum(e.calories for e in day_entries)
        day_protein = sum(e.protein for e in day_entries)
        day_carbs = sum(e.carbs for e in day_entries)
        day_fat = sum(e.fat for e in day_entries)
        
        daily_summaries.append(DailySummary(
            date=current_date,
            total_calories=round(day_calories, 1),
            total_protein=round(day_protein, 1),
            total_carbs=round(day_carbs, 1),
            total_fat=round(day_fat, 1),
            meal_count=len(day_entries),
            meals=day_entries
        ))
        
        total_calories += day_calories
        total_protein += day_protein
        total_carbs += day_carbs
        total_fat += day_fat
        
        current_date += timedelta(days=1)
    
    days_count = (end_date - start_date).days + 1
    
    return WeeklySummary(
        start_date=start_date,
        end_date=end_date,
        total_calories=round(total_calories, 1),
        avg_calories_per_day=round(total_calories / days_count, 1),
        total_protein=round(total_protein, 1),
        total_carbs=round(total_carbs, 1),
        total_fat=round(total_fat, 1),
        daily_summaries=daily_summaries
    )

@app.get("/meal/{meal_type}", response_model=List[CalorieEntryResponse])
def get_entries_by_meal(
    meal_type: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    validate_meal_type(meal_type)
    
    query = db.query(Calories).filter(Calories.meal == meal_type)
    
    if start_date:
        query = query.filter(Calories.date >= start_date)
    if end_date:
        query = query.filter(Calories.date <= end_date)
    
    entries = query.order_by(Calories.date.desc()).all()
    return entries

@app.get("/stats/meals", response_model=List[MealSummary])
def get_meal_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()
    
    entries = db.query(Calories).filter(
        and_(Calories.date >= start_date, Calories.date <= end_date)
    ).all()
    
    meal_data = {}
    for entry in entries:
        if entry.meal not in meal_data:
            meal_data[entry.meal] = {
                'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'count': 0
            }
        meal_data[entry.meal]['calories'] += entry.calories
        meal_data[entry.meal]['protein'] += entry.protein
        meal_data[entry.meal]['carbs'] += entry.carbs
        meal_data[entry.meal]['fat'] += entry.fat
        meal_data[entry.meal]['count'] += 1
    
    return [
        MealSummary(
            meal=meal,
            total_calories=round(data['calories'], 1),
            total_protein=round(data['protein'], 1),
            total_carbs=round(data['carbs'], 1),
            total_fat=round(data['fat'], 1),
            entry_count=data['count']
        )
        for meal, data in meal_data.items()
    ]

@app.get("/stats/macros", response_model=MacroPercentages)
def get_macro_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if start_date is None:
        start_date = date.today() - timedelta(days=7)
    if end_date is None:
        end_date = date.today()
    
    result = db.query(
        func.sum(Calories.protein).label('total_protein'),
        func.sum(Calories.carbs).label('total_carbs'),
        func.sum(Calories.fat).label('total_fat')
    ).filter(
        and_(Calories.date >= start_date, Calories.date <= end_date)
    ).first()
    
    total_protein = result.total_protein or 0
    total_carbs = result.total_carbs or 0
    total_fat = result.total_fat or 0
    
    return calculate_macro_percentages(total_protein, total_carbs, total_fat)

@app.get("/progress/today", response_model=DailyProgress)
def get_today_progress(
    calorie_goal: float = Query(2000, gt=0),
    protein_goal: float = Query(150, gt=0),
    carbs_goal: float = Query(200, gt=0),
    fat_goal: float = Query(65, gt=0),
    db: Session = Depends(get_db)
):
    today = date.today()
    entries = db.query(Calories).filter(Calories.date == today).all()
    
    total_calories = sum(e.calories for e in entries)
    total_protein = sum(e.protein for e in entries)
    total_carbs = sum(e.carbs for e in entries)
    total_fat = sum(e.fat for e in entries)
    
    consumed = DailySummary(
        date=today,
        total_calories=round(total_calories, 1),
        total_protein=round(total_protein, 1),
        total_carbs=round(total_carbs, 1),
        total_fat=round(total_fat, 1),
        meal_count=len(entries),
        meals=entries
    )
    
    goals = NutritionGoals(
        calorie_goal=calorie_goal,
        protein_goal=protein_goal,
        carbs_goal=carbs_goal,
        fat_goal=fat_goal
    )
    
    return DailyProgress(
        date=today,
        consumed=consumed,
        goals=goals,
        remaining_calories=round(calorie_goal - total_calories, 1),
        remaining_protein=round(protein_goal - total_protein, 1),
        remaining_carbs=round(carbs_goal - total_carbs, 1),
        remaining_fat=round(fat_goal - total_fat, 1),
        calorie_progress_percent=round((total_calories / calorie_goal) * 100, 1),
        protein_progress_percent=round((total_protein / protein_goal) * 100, 1),
        carbs_progress_percent=round((total_carbs / carbs_goal) * 100, 1),
        fat_progress_percent=round((total_fat / fat_goal) * 100, 1)
    )

@app.get("/search", response_model=List[CalorieEntryResponse])
def search_entries(
    food: Optional[str] = None,
    meal: Optional[str] = None,
    min_calories: Optional[float] = None,
    max_calories: Optional[float] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Calories)
    
    if food:
        query = query.filter(Calories.food.ilike(f"%{food}%"))
    if meal:
        validate_meal_type(meal)
        query = query.filter(Calories.meal == meal)
    if min_calories:
        query = query.filter(Calories.calories >= min_calories)
    if max_calories:
        query = query.filter(Calories.calories <= max_calories)
    
    entries = query.order_by(Calories.date.desc()).limit(50).all()
    return entries

@app.put("/{entry_id}", response_model=CalorieEntryResponse)
def update_entry(
    entry_id: int,
    update_data: CalorieEntryUpdate,
    db: Session = Depends(get_db)
):
    entry = db.query(Calories).filter(Calories.id == entry_id).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    
    if update_data.meal is not None:
        validate_meal_type(update_data.meal)
        entry.meal = update_data.meal
    if update_data.food is not None:
        entry.food = update_data.food
    if update_data.amount is not None:
        entry.amount = update_data.amount
    if update_data.calories is not None:
        entry.calories = update_data.calories
    if update_data.protein is not None:
        entry.protein = update_data.protein
    if update_data.carbs is not None:
        entry.carbs = update_data.carbs
    if update_data.fat is not None:
        entry.fat = update_data.fat
    if update_data.note is not None:
        entry.note = update_data.note
    
    db.commit()
    db.refresh(entry)
    
    return entry

@app.delete("/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(Calories).filter(Calories.id == entry_id).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    
    db.delete(entry)
    db.commit()
    
    return {"message": f"Eintrag gelöscht: {entry.food}"}

@app.get("/stats/summary")
def get_summary_stats(db: Session = Depends(get_db)):
    total_entries = db.query(func.count(Calories.id)).scalar()
    
    avg_calories = db.query(func.avg(Calories.calories)).scalar() or 0
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    week_result = db.query(
        func.sum(Calories.calories).label('total_calories'),
        func.sum(Calories.protein).label('total_protein'),
        func.sum(Calories.carbs).label('total_carbs'),
        func.sum(Calories.fat).label('total_fat')
    ).filter(Calories.date >= week_ago).first()
    
    unique_foods = db.query(func.count(func.distinct(Calories.food))).scalar()
    
    return {
        "total_entries": total_entries,
        "avg_calories_per_entry": round(avg_calories, 1),
        "unique_foods_tracked": unique_foods,
        "last_7_days": {
            "total_calories": round(week_result.total_calories or 0, 1),
            "avg_per_day": round((week_result.total_calories or 0) / 7, 1),
            "total_protein": round(week_result.total_protein or 0, 1),
            "total_carbs": round(week_result.total_carbs or 0, 1),
            "total_fat": round(week_result.total_fat or 0, 1)
        }
    }