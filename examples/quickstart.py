"""Rewrite a prompt with the bundled US Census distribution, or your own table."""
from promptdiv import apply_prompt_diversity, DiversityModule

# Bundled census. The occupation (or a generic person) is detected from the prompt.
print(apply_prompt_diversity("a photo of a person diving in the water"))
print(apply_prompt_diversity("an ad for a nurse in a hospital"))
print(apply_prompt_diversity("a realistic photo of a construction worker on a site"))
print(apply_prompt_diversity("a person walking", active=False))   # unchanged

# Mixed-race people are described after the noun, not as an adjective list --
# "a Black and Japanese teacher" makes generators draw two people, one of each.
mod = DiversityModule(seed=3)
for _ in range(200):
    out = mod.augment("an ad for a teacher in a classroom")
    if "mixed" in out:
        print(out)
        break

# Your own data: a table of people. Columns are whatever traits you want, and a
# whole row is drawn at a time, so correlations in your table survive.
import pandas as pd
my_base = pd.DataFrame({
    "age":    ["in their 20s", "in their 30s", "in their 40s"],
    "gender": ["female", "male", "female"],
    "race":   ["asian", "white", "black"],
    "weight": [5, 2, 3],           # optional: how common each kind of person is
})
mine = DiversityModule(my_base, sep=", ")
print(mine.augment("a photo of a person shopping online"))
