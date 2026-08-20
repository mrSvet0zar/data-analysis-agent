"""Generate deterministic sample CSVs with built-in correlations and outliers."""

import csv
import math
import random
from pathlib import Path

random.seed(42)
HERE = Path(__file__).parent


def write(name, header, rows):
    with open(HERE / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {name}: {len(rows)} rows")


# 1) sales.csv — marketing spend correlates with revenue, with a few outliers.
rows = []
regions = ["North", "South", "East", "West"]
for i in range(300):
    spend = round(random.uniform(500, 5000), 2)
    revenue = spend * random.uniform(2.5, 3.5) + random.gauss(0, 400)
    units = int(revenue / random.uniform(40, 60))
    if i in (50, 120, 250):  # inject outliers
        revenue *= 4
    rows.append(
        [
            f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            random.choice(regions),
            spend,
            round(max(revenue, 0), 2),
            max(units, 0),
            round(random.uniform(1.5, 4.9), 1),
        ]
    )
write(
    "sales.csv", ["date", "region", "marketing_spend", "revenue", "units_sold", "avg_rating"], rows
)


# 2) employees.csv — age/experience/salary correlated, some missing values.
rows = []
depts = ["Engineering", "Sales", "Marketing", "HR", "Finance"]
for i in range(200):
    age = random.randint(22, 60)
    experience = max(0, age - 22 - random.randint(0, 4))
    salary = 35000 + experience * 2200 + random.gauss(0, 6000)
    satisfaction = round(random.uniform(2.0, 5.0), 1)
    rows.append(
        [
            i + 1,
            random.choice(depts),
            age,
            experience,
            round(max(salary, 30000), 2),
            satisfaction if random.random() > 0.08 else "",  # ~8% missing
        ]
    )
write(
    "employees.csv",
    ["employee_id", "department", "age", "years_experience", "salary", "satisfaction_score"],
    rows,
)


# 3) weather.csv — seasonal temperature time series with humidity.
rows = []
for day in range(365):
    temp = 15 + 12 * math.sin(2 * math.pi * day / 365) + random.gauss(0, 2.5)
    humidity = 70 - 0.8 * temp + random.gauss(0, 5)
    rainfall = max(0, random.gauss(3, 4) - temp * 0.05)
    rows.append(
        [
            f"day_{day + 1:03d}",
            round(temp, 1),
            round(min(max(humidity, 10), 100), 1),
            round(rainfall, 1),
            random.randint(0, 100),
        ]
    )
write(
    "weather.csv", ["day", "temperature_c", "humidity_pct", "rainfall_mm", "cloud_cover_pct"], rows
)
