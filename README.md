# promptdiv

[![DOI](https://zenodo.org/badge/1330875509.svg)](https://doi.org/10.5281/zenodo.21889100)

Census-grounded prompt augmentation for text-to-image models.

Text-to-image models (FLUX, Stable Diffusion / SDXL, hosted APIs) tend to produce a narrow set of people: mostly White, young, and locked to occupational stereotypes. `promptdiv` rewrites the prompt before generation so the person described is drawn from a real demographic distribution. You keep writing prompts as usual, for example `"a person ..."` or `"a nurse ..."`, and when the module is on it inserts a short description drawn from US Census microdata. Turn it off and the prompt is unchanged.

It works with any model because it only edits the prompt text, and the occupation (or a generic person) is detected from the prompt.

```python
from promptdiv import apply_prompt_diversity

apply_prompt_diversity("a photo of a person diving in the water")
# "a photo of a 56-year-old Filipino male person diving in the water"

apply_prompt_diversity("an ad for a nurse in a hospital")
# "an ad for a 32-year-old White female nurse in a hospital"
```

## Installation

```bash
pip install promptdiv
```

From source: `git clone https://github.com/TijmenJansen0/prompt-div && cd prompt-div && pip install -e .`

The bundled US Census distribution is included, so nothing else is needed.

## What makes the draws realistic

Two design choices do most of the work, and both matter more than they sound.

**A whole person is drawn, not three separate traits.** Each draw takes one real census respondent's age, race and gender *together*. Sampling them independently would give you the right marginal percentages and the wrong people — because nurses skew female, CEOs skew older and Whiter, and construction workers skew male and Hispanic. Independent draws erase exactly the structure the module exists to reproduce.

**Race is asked for in detail, not in four buckets.** The distribution carries the census's own detailed categories — Filipino, Navajo, Mexican, Vietnamese, Samoan, and 70-odd more — because "a person of colour" is not something a generator can draw, and asking for one of four coarse classes flattens the very minorities the tool is meant to include.

Mixed-race people get a phrasing of their own. `"a Black and Japanese construction worker"` reads to a generator as a **list** and reliably produces two people, one of each. So a pair of origins is written after the noun instead:

```python
apply_prompt_diversity("an ad for a teacher in a classroom")
# "an ad for a 39-year-old female teacher of mixed White and Vietnamese heritage in a classroom"
```

## Usage

One function plus an on/off switch. Wire the switch to a config flag so you do not have to branch your own code.

```python
from promptdiv import apply_prompt_diversity

apply_prompt_diversity("a professional ad photo of a person in an office")
# "a professional ad photo of a 47-year-old White male person in an office"

apply_prompt_diversity("a person walking", active=False)   # unchanged
```

If the prompt names one of the built-in occupations, the description is placed before it and drawn from that occupation's real mix. Otherwise the prompt is treated as a generic `person` (a built-in group whose distribution is the whole US adult population), and the description is placed before the word "person".

Each call is an independent draw, so a batch of images comes out as a representative spread. When several names appear, the longest occupation wins (`"truck driver"` over `"driver"`), and a named occupation is preferred over the generic `person`. Pass `seed=` to `DiversityModule` when you need the same batch twice.

<details>
<summary>Built-in occupations (85)</summary>

Accountant, Administrative Manager, Air Traffic Controller, Animal Caretaker, Artist, Athlete, Attendant, Auto Mechanic, Baker, Bank Teller, Barber, Bartender, Billing Specialist, Bus Driver, Business Manager, CEO, Carpenter, Cashier, Chef, Childcare Worker, Civil Engineer, Cleaner, Construction Worker, Cook, Counselor, Dental Nurse, Dentist, Designer, Dietitian, Doctor, Driver, Editor, Electrician, Engineering Technician, Farmer, Firefighter, Fitness Worker, Gaming Attendant, Hairdresser, Hotel Attendant, Kitchen Helper, Landscaper, Lawyer, Librarian, Logger, Machinist, Mail Carrier, Medical Technician, Miner, Model Maker, Nurse, Operations Manager, Packager, Personal Care Specialist, Photographer, Physical Therapist, Pilot, Plumber, Police Officer, Porter, Producer, Production Worker, Rail Worker, Real Estate Broker, Religious Leader, Sailor, Salesperson, Scientist, Secretary, Security Guard, Social Worker, Software Developer, Soldier, Stock Clerk, Surveying Technician, Taxi Driver, Teacher, Technician, Therapist, Truck Driver, Unemployed, Veterinarian, Waiter, Welder, Writer.
</details>

## Apply to a model

Wrap the pipeline once with `enable_diversity`, then pass `apply_prompt_diversity=True` in the call. Nothing else about your generation code changes.

```python
import torch
from diffusers import FluxPipeline
from promptdiv import enable_diversity

pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-dev",
                                    torch_dtype=torch.bfloat16).to("cuda")
pipe = enable_diversity(pipe)

image = pipe(
    prompt="a professional ad photo of a person in an office",
    apply_prompt_diversity=True,
    num_inference_steps=30, guidance_scale=3.5,
    height=512, width=512, max_sequence_length=512,
).images[0]
```

The same wrapper works for any `diffusers` pipeline (swap `FluxPipeline` for `StableDiffusionXLPipeline`, etc.). For a hosted API that takes a text string, rewrite the prompt directly instead:

```python
from promptdiv import apply_prompt_diversity
client.images.generate(model="gpt-image-1.5",
                       prompt=apply_prompt_diversity("a person presenting to a boardroom"))
```

## Use your own data

The census default is only a default. The distribution is just a table, and the module does not hard-code what the columns mean. Keep age / race / gender, or swap them for **region, age, gender, and profession**, or any other traits — whatever columns you provide become the description, in the order they appear.

Point the module at your table and use it the same way:

```python
from promptdiv import DiversityModule, enable_diversity

mine = DiversityModule("my_distribution.csv")   # or a pandas DataFrame
mine.augment("a photo of a person on a beach")

pipe = enable_diversity(pipe, module=mine)      # to use it with a model
```

There are two ways to write the table; the module detects which you used.

**1. A table of people (recommended).** One row per kind of person, one column per trait, for example `age, gender, race`. Optionally add a `weight` column for how common that kind of person is (leave it out to weight every row equally). Save as CSV or Excel and point the module at it.

| age | gender | race | weight |
|---|---|---|---|
| 20-35 years old | female | asian | 5 |
| 20-35 years old | male | white | 2 |
| 36-50 years old | female | black | 3 |

Write each value the way it should read in the prompt (`20-35 years old`, not `20-35`), because it is inserted verbatim. The one exception is a column named `age` holding plain numbers, which is written as `"34-year-old"`.

**A whole row is drawn at a time**, so any real correlations in your data survive, and the output proportions match your table. This is the shape the bundled census uses and the one the paper evaluates.

Different traits entirely — just change the columns. For example, matching a brand's own customer base:

| age | gender | region | weight |
|---|---|---|---|
| 20-35 years old | female | urban | 4 |
| 36-50 years old | male | suburban | 2 |
| 51-70 years old | female | rural | 1 |

→ `"a photo of a 20-35 years old female urban person shopping online"`

To see or export the percentages your table implies, call `.to_percentages()`:

```python
DiversityModule("my_people.csv").to_percentages()   # -> group, attribute, value, pct
```

**2. Percentages.** If you know the shares but not the people, provide them directly with columns `attribute, value, pct`.

| attribute | value | pct |
|---|---|---|
| gender | female | 70 |
| gender | male | 30 |
| age | gen-z | 60 |
| age | millennial | 40 |

This is easier to hand-write, but each attribute is then drawn **independently**, so any correlation between them is lost. Prefer a table of people when you have one.

### Conditioning on a word in the prompt (like occupations)

Add a `group` column (or name it `occupation`) to give each group its own distribution. Its value is matched in the prompt, the matching subset is used, and the description is inserted around that word. This is exactly how the built-in occupations work. Leave the `group` column out and one distribution applies to every prompt. Add a `person` group as the fallback for prompts that name no group (the bundled census does this).

### Text that belongs after the noun

Add a `post` column for text that has to follow the subject rather than precede it. Where it is non-empty it is inserted after the matched noun; where it is empty nothing is added. The bundled census uses it for the mixed-race phrasing described above, and you can use it for anything that reads badly as an adjective.

| age | gender | race | post | weight |
|---|---|---|---|---|
| 39 | female | | of mixed White and Vietnamese heritage | 3 |
| 45 | male | Korean | | 8 |

### What to watch out for

- **Values are inserted verbatim.** Control the wording through the value strings themselves (`"in their 30s"`, `"aged 25-34"`, `"young"`). Set the separator with `DiversityModule(..., sep=", ")`; it defaults to a single space.
- **Column order = description order.** Reorder columns, or pass `attribute_order=["age", "race", "gender"]`.
- **Grouping needs a word in the prompt.** It only helps when the group value (e.g. an occupation) actually appears in your prompts. For "make everyone match my customers", skip the group column and use one distribution.
- **Weights are optional.** With tables of people, no `weight` means every row is equally likely; with percentage tables, `pct` (or `weight`/`count`) sets the shares.
- Load from CSV or Excel by passing a DataFrame: `DiversityModule(pd.read_excel("my.xlsx"))`.

## Bundled dataset

`promptdiv/data/census.csv.gz` holds one row per distinct kind of adult, per occupation, with that kind's summed person-weight: columns `group` (85 occupations plus `person` for the whole adult population), `age`, `race`, `gender`, `post`, `weight`. It was built from US Census microdata (IPUMS ACS) — sex, single-year age, the detailed race and Hispanic-origin codes, and occupation — with the 462 detailed occupations grouped into 85. Collapsing identical people into weighted cells keeps the joint distribution **exact** rather than approximated by a sample, and keeps the file small (163,753 rows, under 1 MB).

`promptdiv/data/occupation_mapping.csv` is the 462 → 85 crosswalk. `tools/build_census.py` and `tools/phrasing.py` are the code that produced the table, so the derivation is readable rather than taken on trust. Running it needs your own IPUMS extract (the microdata are not redistributable); point `IPUMS_BASE` at it.

**Adults only (18+).** The paper measures adults, and a tool that rewrites prompts for image generators should not be asking them to render children.

Raw IPUMS microdata are not redistributed here (IPUMS licensing); the package ships aggregated weighted cell counts.

## Evaluation

Across the advertising corpus in the accompanying paper, on FLUX.1-dev:

- **Occupational representation.** Over the 23 occupations with at least 200 advertisements, the mean distance to the US adult population fell from **14.5 to 7.3 percentage points** — closer in **23 of 23** occupations (Wilcoxon signed-rank, p = 2.4 × 10⁻⁷). Real US advertising sits at 9.6, so the census-augmented output is closer to the population than real advertising is.
- **Amplification.** Regressing each source's occupational share of women on the census share, default FLUX has a slope of **1.10** — it exaggerates real occupational gender skew — while the module sits at **1.00**. Real advertising compresses it, at 0.71.
- **Marginals.** Black representation moved from 4.1% to 11.4% (population 11.6%); women from 54.0% to 48.1% (population 51.0%); adults 65+ from 0.6% to 26.4% (population 21.6%).

In a preregistered experiment (N = 193, 7-point scales), census-augmented ads were rated more diverse (2.85 → 4.22) and more representative (3.86 → 4.63) than default FLUX ads, and also **more appealing** (3.95 → 4.44) — the gain did not cost appeal. Felt self-relevance rose most for viewers from under-represented groups (+1.07, n = 130) and did not fall for anyone else (+0.21, n = 62; difference p = .011).

**What it cannot do.** Prompt augmentation can only realign what the model will actually draw, and the gap between the ask and the render is real. Traced end to end for the paper's smallest and hardest group, the module **asked** for a non-White, non-Black, non-Asian person in 22.0% of prompts; 15.8% survived as a descriptor the census could name renderably, human raters saw one in 9.2%, and an automated classifier detected 7.2%. Roughly two fifths of the shortfall is the generator declining to draw what it was asked for, and most of the rest is the census carrying codes that name no renderable appearance. A request is not a guarantee.

## Citation

Software archived on Zenodo: https://doi.org/10.5281/zenodo.21889100 (this DOI always resolves to the latest release).

```bibtex
@software{jansen_promptdiv,
  author    = {Jansen, Tijmen},
  title     = {promptdiv: census-grounded prompt augmentation for text-to-image models},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21889100},
  url       = {https://doi.org/10.5281/zenodo.21889100}
}

@article{jansen2026promptdiv,
  title   = {Census-grounded prompt augmentation reduces demographic misrepresentation in AI-generated advertising},
  author  = {Jansen, Tijmen},
  year    = {2026},
  note    = {Manuscript in preparation}
}
```

## License

MIT (see `LICENSE`). The bundled demographic summaries are derived from US Census microdata accessed via IPUMS; please acknowledge IPUMS when you use them.
