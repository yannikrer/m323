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
    DailyProgress,
)
from app.utils.fp import (
    group_by,
    sum_by,
    flat_map,
    validator,
)

app = APIRouter()

MEAL_TYPES = ["Frühstück", "Mittagessen", "Abendessen", "Snack"]


# ── Validators (Closures) ─────────────────────────────────────

valid_meal = validator(
    lambda m: m in MEAL_TYPES,
    f"Ungultiger Mahlzeittyp. Erlaubt: {', '.join(MEAL_TYPES)}"
)
positive_float = validator(
    lambda x: isinstance(x, (int, float)) and x > 0,
    "Wert muss positiv sein"
)


# ── Pure Functions ─────────────────────────────────────────────

def validate_meal_type(meal: str) -> str:
    """Pure: Mahlzeittyp validieren."""
    return valid_meal(meal)


def calculate_macro_percentages(
    protein: float, carbs: float, fat: float
) -> MacroPercentages:
    """Pure: Makro-Prozentsatze berechnen."""
    protein_cal = protein * 4
    carbs_cal = carbs * 4
    fat_cal = fat * 9
    total_cal = protein_cal + carbs_cal + fat_cal

    if total_cal == 0:
        return MacroPercentages(
            protein_percent=0, carbs_percent=0, fat_percent=0,
            protein_grams=protein, carbs_grams=carbs, fat_grams=fat,
        )

    return MacroPercentages(
        protein_percent=round((protein_cal / total_cal) * 100, 1),
        carbs_percent=round((carbs_cal / total_cal) * 100, 1),
        fat_percent=round((fat_cal / total_cal) * 100, 1),
        protein_grams=protein,
        carbs_grams=carbs,
        fat_grams=fat,
    )



def calculate_totals(entries: List[Calories]) -> dict:
    """Pure: Alle Totals berechnen mit HOFs."""
    return {
        "calories": sum_by(lambda e: e.calories)(entries),
        "protein": sum_by(lambda e: e.protein)(entries),
        "carbs": sum_by(lambda e: e.carbs)(entries),
        "fat": sum_by(lambda e: e.fat)(entries),
    }


def create_daily_summary(target_date: date, entries: List[Calories]) -> DailySummary:
    """Pure: DailySummary erstellen."""
    totals = calculate_totals(entries)
    return DailySummary(
        date=target_date,
        total_calories=round(totals["calories"], 1),
        total_protein=round(totals["protein"], 1),
        total_carbs=round(totals["carbs"], 1),
        total_fat=round(totals["fat"], 1),
        meal_count=len(entries),
        meals=entries,
    )


def group_entries_by_date(entries: List[Calories]) -> dict:
    """Pure: Entries nach Datum gruppieren (rekursiv via group_by)."""
    return group_by(lambda e: e.date)(entries)


def calculate_progress_percent(current: float, goal: float) -> float:
    """Pure: Fortschritt in Prozent."""
    return round((current / goal) * 100, 1) if goal > 0 else 0


# ── DB Service Functions ───────────────────────────────────────

def get_entry_by_id(db: Session, entry_id: int) -> Calories | None:
    return db.query(Calories).filter(Calories.id == entry_id).first()


def create_calorie_entry(db: Session, data: CalorieEntryCreate) -> Calories:
    entry = Calories(
        date=data.date, meal=data.meal, food=data.food,
        amount=data.amount, calories=data.calories,
        protein=data.protein, carbs=data.carbs, fat=data.fat, note=data.note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_entries_by_date(db: Session, target_date: date) -> List[Calories]:
    return db.query(Calories).filter(Calories.date == target_date).all()


def get_entries_in_range(db: Session, start: date, end: date) -> List[Calories]:
    return (
        db.query(Calories)
        .filter(and_(Calories.date >= start, Calories.date <= end))
        .all()
    )


def delete_entry_by_id(db: Session, entry_id: int) -> Calories | None:
    entry = get_entry_by_id(db, entry_id)
    if entry:
        db.delete(entry)
        db.commit()
    return entry


def build_update_dict(data: CalorieEntryUpdate) -> dict:
    """Pure: Update-Dictionary bauen mit Validierung."""
    fields = {
        "meal": data.meal, "food": data.food, "amount": data.amount,
        "calories": data.calories, "protein": data.protein,
        "carbs": data.carbs, "fat": data.fat, "note": data.note,
    }
    return {
        k: (validate_meal_type(v) if k == "meal" else v)
        for k, v in fields.items()
        if v is not None
    }


# ── Route Handlers ─────────────────────────────────────────────

@app.post("/", response_model=CalorieEntryResponse, status_code=201)
def create_calorie_entry_route(entry: CalorieEntryCreate, db: Session = Depends(get_db)):
    validate_meal_type(entry.meal)
    db_entry = create_calorie_entry(db, entry)
    return db_entry


@app.get("/", response_model=List[CalorieEntryResponse])
def get_all_entries(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    entries = (
        db.query(Calories)
        .order_by(Calories.date.desc(), Calories.id.desc())
        .offset(skip).limit(limit).all()
    )
    return entries


@app.get("/today", response_model=DailySummary)
def get_today_entries(db: Session = Depends(get_db)):
    entries = get_entries_by_date(db, date.today())
    return create_daily_summary(date.today(), entries)


@app.get("/date/{target_date}", response_model=DailySummary)
def get_entries_by_date_route(target_date: date, db: Session = Depends(get_db)):
    entries = get_entries_by_date(db, target_date)
    return create_daily_summary(target_date, entries)


@app.get("/week", response_model=WeeklySummary)
def get_week_summary(start_date: Optional[date] = None, db: Session = Depends(get_db)):
    if start_date is None:
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
    else:
        end_date = start_date + timedelta(days=6)

    entries = get_entries_in_range(db, start_date, end_date)
    grouped = group_entries_by_date(entries)

    daily_summaries = list(map(
        lambda d: create_daily_summary(d, grouped.get(d, [])),
        (start_date + timedelta(days=i) for i in range(7)),
    ))

    totals = calculate_totals(entries)
    days_count = (end_date - start_date).days + 1

    return WeeklySummary(
        start_date=start_date,
        end_date=end_date,
        total_calories=round(totals["calories"], 1),
        avg_calories_per_day=round(totals["calories"] / days_count, 1),
        total_protein=round(totals["protein"], 1),
        total_carbs=round(totals["carbs"], 1),
        total_fat=round(totals["fat"], 1),
        daily_summaries=daily_summaries,
    )


@app.get("/meal/{meal_type}", response_model=List[CalorieEntryResponse])
def get_entries_by_meal(
    meal_type: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    validate_meal_type(meal_type)

    query = db.query(Calories).filter(Calories.meal == meal_type)
    if start_date:
        query = query.filter(Calories.date >= start_date)
    if end_date:
        query = query.filter(Calories.date <= end_date)

    return query.order_by(Calories.date.desc()).all()


@app.get("/stats/meals", response_model=List[MealSummary])
def get_meal_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start = start_date or date.today() - timedelta(days=30)
    end = end_date or date.today()

    entries = get_entries_in_range(db, start, end)

    meal_data = flat_map(
        lambda entry: [{
            "meal": entry.meal,
            "calories": entry.calories,
            "protein": entry.protein,
            "carbs": entry.carbs,
            "fat": entry.fat,
        }],
        entries,
    )

    aggregated = group_by(lambda d: d["meal"])(meal_data)

    return [
        MealSummary(
            meal=meal,
            total_calories=round(sum_by(lambda d: d["calories"])(items), 1),
            total_protein=round(sum_by(lambda d: d["protein"])(items), 1),
            total_carbs=round(sum_by(lambda d: d["carbs"])(items), 1),
            total_fat=round(sum_by(lambda d: d["fat"])(items), 1),
            entry_count=len(items),
        )
        for meal, items in aggregated.items()
    ]


@app.get("/stats/macros", response_model=MacroPercentages)
def get_macro_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    start = start_date or date.today() - timedelta(days=7)
    end = end_date or date.today()

    result = (
        db.query(
            func.sum(Calories.protein).label("total_protein"),
            func.sum(Calories.carbs).label("total_carbs"),
            func.sum(Calories.fat).label("total_fat"),
        )
        .filter(and_(Calories.date >= start, Calories.date <= end))
        .first()
    )

    return calculate_macro_percentages(
        result.total_protein or 0,
        result.total_carbs or 0,
        result.total_fat or 0,
    )


@app.get("/progress/today", response_model=DailyProgress)
def get_today_progress(
    calorie_goal: float = Query(2000, gt=0),
    protein_goal: float = Query(150, gt=0),
    carbs_goal: float = Query(200, gt=0),
    fat_goal: float = Query(65, gt=0),
    db: Session = Depends(get_db),
):
    entries = get_entries_by_date(db, date.today())
    totals = calculate_totals(entries)

    consumed = create_daily_summary(date.today(), entries)
    goals = NutritionGoals(
        calorie_goal=calorie_goal, protein_goal=protein_goal,
        carbs_goal=carbs_goal, fat_goal=fat_goal,
    )

    return DailyProgress(
        date=date.today(),
        consumed=consumed,
        goals=goals,
        remaining_calories=round(calorie_goal - totals["calories"], 1),
        remaining_protein=round(protein_goal - totals["protein"], 1),
        remaining_carbs=round(carbs_goal - totals["carbs"], 1),
        remaining_fat=round(fat_goal - totals["fat"], 1),
        calorie_progress_percent=calculate_progress_percent(totals["calories"], calorie_goal),
        protein_progress_percent=calculate_progress_percent(totals["protein"], protein_goal),
        carbs_progress_percent=calculate_progress_percent(totals["carbs"], carbs_goal),
        fat_progress_percent=calculate_progress_percent(totals["fat"], fat_goal),
    )


@app.get("/search", response_model=List[CalorieEntryResponse])
def search_entries(
    food: Optional[str] = None,
    meal: Optional[str] = None,
    min_calories: Optional[float] = None,
    max_calories: Optional[float] = None,
    db: Session = Depends(get_db),
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

    return query.order_by(Calories.date.desc()).limit(50).all()


@app.put("/{entry_id}", response_model=CalorieEntryResponse)
def update_entry(
    entry_id: int, update_data: CalorieEntryUpdate, db: Session = Depends(get_db)
):
    entry = get_entry_by_id(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    updates = build_update_dict(update_data)
    for field, value in updates.items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)
    return entry


@app.delete("/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = delete_entry_by_id(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"message": f"Eintrag geloscht: {entry.food}"}


@app.get("/stats/summary")
def get_summary_stats(db: Session = Depends(get_db)):
    total_entries = db.query(func.count(Calories.id)).scalar() or 0
    avg_calories = db.query(func.avg(Calories.calories)).scalar() or 0

    week_ago = date.today() - timedelta(days=7)

    week_result = db.query(
        func.sum(Calories.calories).label("total_calories"),
        func.sum(Calories.protein).label("total_protein"),
        func.sum(Calories.carbs).label("total_carbs"),
        func.sum(Calories.fat).label("total_fat"),
    ).filter(Calories.date >= week_ago).first()

    unique_foods = db.query(func.count(func.distinct(Calories.food))).scalar() or 0

    return {
        "total_entries": total_entries,
        "avg_calories_per_entry": round(avg_calories, 1),
        "unique_foods_tracked": unique_foods,
        "last_7_days": {
            "total_calories": round(week_result.total_calories or 0, 1),
            "avg_per_day": round((week_result.total_calories or 0) / 7, 1),
            "total_protein": round(week_result.total_protein or 0, 1),
            "total_carbs": round(week_result.total_carbs or 0, 1),
            "total_fat": round(week_result.total_fat or 0, 1),
        },
    }
