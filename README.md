# Gym Tracker - Functional Programming Project

A fitness tracking web application built with **FastAPI** and **Python**, following **functional programming principles** throughout the entire codebase.

## Setup

```bash
# Install dependencies
pip install fastapi uvicorn sqlalchemy httpx jinja2 pydantic

# Start Ollama (required for meal plan generation)
ollama serve
ollama pull llama3.2

# Run the application
uvicorn main:app --reload

# Open in browser
# http://127.0.0.1:8000
```

## Features

- **Water Tracker** - Track daily water intake with quick-add buttons, progress bars, and weekly statistics
- **Calorie Tracker** - Log meals with automatic macro tracking, configurable nutrition goals (5 diet types), and real-time progress visualization
- **Meal Plan Generator** - AI-powered personalized nutrition plans using Ollama/Llama3.2, with live streaming, Markdown rendering, and persistent storage
- **Running Tracker** - Log running sessions with auto-calculated speed/calories, personal bests, goal tracking, and search/filter

## Architecture

```
m323/
├── main.py                    # FastAPI app, Jinja2 setup, page routes
├── app/
│   ├── database/
│   │   └── db.py              # SQLAlchemy models, session management
│   ├── routers/
│   │   ├── water_counter.py   # Water API (pure functions + DB service)
│   │   ├── calories.py        # Calorie API (HOFs, curried extractors)
│   │   ├── planner.py         # Meal plan API (pipe/compose, validators)
│   │   └── running.py         # Running API (pure calculations, closures)
│   ├── schemas/
│   │   ├── water_counter.py   # Frozen Pydantic models (immutable)
│   │   ├── calories.py        # Frozen Pydantic models with validation
│   │   ├── planner.py         # Frozen request/response types
│   │   └── running.py         # Frozen session/stats/goal types
│   ├── templates/
│   │   ├── base.html           # Tailwind CSS layout, sidebar nav
│   │   ├── water.html          # Water tracker frontend
│   │   ├── calories.html       # Calorie tracker frontend
│   │   ├── mealplan.html       # Meal plan generator frontend
│   │   └── running.html        # Running tracker frontend
│   └── utils/
│       └── fp.py               # FP utilities (pipe, compose, curry, etc.)
```

### FP Design Pattern

Every router follows the same layered architecture:

1. **Pure Functions** - No side effects, no mutations. All business logic (calculations, transformations, validations) lives here
2. **DB Service Functions** - The only place with side effects (database I/O). Isolated at system boundaries
3. **Route Handlers** - Thin orchestration layer that composes pure functions with DB calls

```
Request → Route Handler → Pure Function(s) → DB Service → Response
```

## Functional Programming Concepts

### Pure Functions & No Side Effects

All business logic is in pure functions that have no side effects and always produce the same output for the same input:

```python
def calculate_bmi(weight: float, height_cm: float) -> float:
    return round(weight / ((height_cm / 100) ** 2), 1)

def calculate_speed(distance_km: float, duration_minutes: float) -> float:
    return 0 if duration_minutes == 0 else round((distance_km / duration_minutes) * 60, 2)
```

Side effects (database operations) are isolated in dedicated service functions at system boundaries.

### Immutability

All Pydantic schemas use `frozen=True` to enforce immutability at runtime:

```python
class WaterEntryResponse(BaseModel, frozen=True):
    id: int
    datum: date
    menge_ml: int
    ziel_ml: int
    prozent: float
```

Data transformations create new objects instead of mutating existing ones:

```python
def update_entry_fields_pure(entry_data: dict, update: WaterEntryUpdate) -> dict:
    updates = {k: v for k, v in [("menge_ml", update.menge_ml), ("ziel_ml", update.ziel_ml)] if v is not None}
    return merge(entry_data, updates)  # Returns new dict, never mutates input
```

### Higher-Order Functions

HOFs are used extensively for data transformations:

```python
# Curried extractors composed with sum_by
sum_by(lambda e: e.calories)(entries)
sum_by(lambda e: e.protein)(entries)

# map for transformations
list(map(create_water_response, entries))

# flat_map for nested transformations
flat_map(lambda entry: [{...}], entries)
```

Custom HOFs defined in `fp.py`: `pipe`, `compose`, `curry`, `apply_if`, `apply_when_some`, `pick`, `omit`, `filter_by`, `group_by`, `sum_by`, `flat_map`.

### Function Composition

Small, focused functions are composed into pipelines using `pipe` and `compose`:

```python
from app.utils.fp import pipe, compose, merge

def build_prompt(data: MealPlanRequest) -> str:
    bmi = calculate_bmi(data.weight, data.height)
    foods = format_foods(data.favorite_foods)
    return f"...{bmi}...{foods}...".strip()

def create_plan_dict(data: MealPlanRequest, plan_text: str) -> dict:
    return merge({"plan": plan_text}, {"age": data.age, ...})
```

### Recursion / Pattern Matching / Closures

**Recursion**: `group_by` uses recursive list processing instead of imperative loops:

```python
def group_by(key_fn):
    def _group(items):
        def recurse(remaining, acc):
            if not remaining:
                return acc
            head, *tail = remaining
            key = key_fn(head)
            return recurse(tail, merge(acc, {key: acc.get(key, []) + [head]}))
        return recurse(items, {})
    return _group
```

**Closures**: Validators are closures that capture their check and error message:

```python
def validator(check, error_msg):
    def validate(value):
        if not check(value):
            raise ValueError(error_msg)
        return value
    return validate

valid_age = validator(lambda a: 1 <= a <= 120, "Invalid age")
valid_meal = validator(lambda m: m in MEAL_TYPES, "Invalid meal type")
```

### Type Safety

All data shapes are defined with typed, frozen Pydantic models. Field constraints enforce invariants:

```python
class RunningSessionCreate(BaseModel, frozen=True):
    distance_km: float = Field(gt=0)
    duration_minutes: float = Field(gt=0)
    heart_rate_avg: Optional[int] = None
```

Union types used for optional fields, generics in FP utilities via TypeVar.

## Testing

Each pure function can be tested independently without any mocks or database setup:

```python
# test_fp_utils.py
from app.utils.fp import pipe, curry, merge, group_by, validator

def test_pipe():
    double = lambda x: x * 2
    add_one = lambda x: x + 1
    assert pipe(double, add_one)(3) == 7

def test_curry():
    add = curry(lambda a, b: a + b)
    assert add(1)(2) == 3
    assert add(1, 2) == 3

def test_merge():
    assert merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

def test_group_by():
    items = [{"t": "a", "v": 1}, {"t": "b", "v": 2}, {"t": "a", "v": 3}]
    result = group_by(lambda x: x["t"])(items)
    assert len(result["a"]) == 2

def test_validator():
    v = validator(lambda x: x > 0, "must be positive")
    assert v(5) == 5
    try:
        v(-1)
        assert False
    except ValueError:
        pass

# test_pure_functions.py
from app.routers.water_counter import calculate_percentage, is_goal_reached, add_water_pure
from app.routers.running import calculate_speed, estimate_calories, safe_divide
from app.routers.planner import calculate_bmi, format_foods, build_prompt
from app.routers.calories import calculate_macro_percentages, calculate_progress_percent

def test_calculate_percentage():
    assert calculate_percentage(1000, 2000) == 50.0
    assert calculate_percentage(500, 0) == 0.0

def test_calculate_speed():
    assert calculate_speed(10, 60) == 10.0
    assert calculate_speed(5, 0) == 0

def test_estimate_calories():
    assert estimate_calories(10) == 600.0
    assert estimate_calories(10, 70) == 600.0

def test_safe_divide():
    assert safe_divide(10, 2) == 5.0
    assert safe_divide(10, 0) == 0

def test_calculate_bmi():
    assert calculate_bmi(75, 180) == 23.1

def test_add_water_pure():
    assert add_water_pure(1000, 500) == 1500

def test_calculate_macro_percentages():
    result = calculate_macro_percentages(100, 100, 50)
    assert result.protein_percent > 0
    assert result.carbs_percent > 0
    assert result.fat_percent > 0

def test_calculate_progress_percent():
    assert calculate_progress_percent(1000, 2000) == 50.0
    assert calculate_progress_percent(500, 0) == 0

# Run tests
# pytest test_fp_utils.py test_pure_functions.py
```

## Team

| Member | Responsibility |
|--------|---------------|
| Amir | Infrastructure, Water Tracker, Running Schemas |
| Yannik | Calorie Tracker (API + Schema + Frontend) |
| Luka | Meal Plan Generator, Running Tracker |
