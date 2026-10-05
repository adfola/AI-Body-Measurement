import csv
import statistics as st
from collections import defaultdict

errors = defaultdict(list)
with open("validation.csv", newline="", encoding="utf-8") as source:
    for row in csv.DictReader(source):
        errors[row["measure"]].append(float(row["app_cm"]) - float(row["tape_cm"]))

print(f"{'measure':<16}{'n':>3}{'MAE':>7}{'bias':>7}{'max':>7}")
for measure, values in errors.items():
    print(
        f"{measure:<16}{len(values):>3}{st.mean(map(abs, values)):>7.2f}"
        f"{st.mean(values):>7.2f}{max(map(abs, values)):>7.2f}"
    )
