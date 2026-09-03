"""Use your own distribution instead of the bundled census.

Make a CSV (or Excel) of people, then point the module at it. Each value is
inserted into the prompt exactly as written, so phrase the cells the way they
should read (e.g. "20-35 years old", not "20-35"). The one exception is a column
named `age` holding plain numbers, which is written as "34-year-old".
"""
import pandas as pd
from promptdiv import DiversityModule

# 1) your data -- a table of people (weight is optional)
people = pd.DataFrame({
    "age":    ["20-35 years old", "20-35 years old", "36-50 years old"],
    "gender": ["female", "male", "female"],
    "race":   ["asian", "white", "black"],
    "weight": [5, 2, 3],
})
# or load from a file: people = pd.read_csv("my_people.csv")  /  pd.read_excel("my_people.xlsx")

# 2) build the module on your data
mod = DiversityModule(people, sep=", ")

# 3a) rewrite prompts directly
print(mod.augment("a professional ad photo of a person in an office"))

# 3b) or attach it to an image pipeline:
# from promptdiv import enable_diversity
# pipe = enable_diversity(pipe, module=mod)
# pipe(prompt="... a person ...", apply_prompt_diversity=True)

# A `post` column holds text that belongs AFTER the subject noun rather than
# before it -- useful for anything that reads badly as an adjective.
pairs = pd.DataFrame({
    "age":    [39, 45],
    "race":   ["", "Korean"],
    "gender": ["female", "male"],
    "post":   ["of mixed White and Vietnamese heritage", ""],
    "weight": [1, 1],
})
mixed = DiversityModule(pairs, seed=1)
seen = {mixed.augment("an ad for a person in a classroom") for _ in range(20)}
for line in sorted(seen):
    print(line)

# optional: see the percentages your table implies (census-style table)
print(mod.to_percentages())
