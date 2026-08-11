# promptdiv

Census-grounded prompt augmentation for text-to-image models.

Text-to-image models (FLUX, Stable Diffusion / SDXL, hosted APIs) tend to produce a narrow set of people: mostly White, young, and locked to occupational stereotypes. `promptdiv` rewrites the prompt before generation so the person described is sampled from a demographic distribution. You keep writing prompts as usual, for example `"a person ..."` or `"a nurse ..."`, and when the module is on it inserts a short description (by default age, race, gender) drawn from US Census data. Turn it off and the prompt is unchanged.

It works with any model because it only edits the prompt text, and the occupation (or a generic person) is detected from the prompt.

```python
from promptdiv import apply_prompt_diversity

apply_prompt_diversity("a photo of a person diving in the water")
# "a photo of a 25-34 years old, hispanic, male person diving in the water"

apply_prompt_diversity("an ad for a nurse in a hospital")
# "an ad for a 25-34 years old, white, female nurse in a hospital"
```

## Installation

```bash
pip install promptdiv
```

From source: `git clone https://github.com/tijmenjansen/prompt-div && cd prompt-div && pip install -e .`

The bundled US Census distribution is included, so nothing else is needed.

## Usage

One function plus an on/off switch. Wire the switch to a config flag so you do not have to branch your own code.

```python
from promptdiv import apply_prompt_diversity

apply_prompt_diversity("a professional ad photo of a person in an office")
# "a professional ad photo of a 35-44 years old, white, male person in an office"

apply_prompt_diversity("a person walking", active=False)   # unchanged
```

If the prompt names one of the built-in occupations, the description is placed before it and sampled from that occupation's real mix. Otherwise the prompt is treated as a generic `person` (a built-in group whose distribution is the whole US population), and the description is placed before the word "person":

```python
apply_prompt_diversity("a person")
# "a 16-24 years old, white, female person"
```

Each call is an independent draw, so a batch of images comes out as a representative spread. When several names appear, the longest occupation wins (`"truck driver"` over `"driver"`), and a named occupation is preferred over the generic `person`.

<details>
<summary>Built-in occupations (84)</summary>

Accountant, Administrative Manager, Air Traffic Controller, Animal Caretaker, Artist, Athlete, Attendant, Auto Mechanic, Baker, Bank Teller, Barber, Bartender, Billing Specialist, Bus Driver, Business Manager, CEO, Carpenter, Cashier, Chef, Childcare Worker, Civil Engineer, Cleaner, Construction Worker, Cook, Counselor, Dentist, Designer, Dietitian, Doctor, Driver, Editor, Electrician, Engineering Technician, Farmer, Firefighter, Fitness Worker, Gaming Attendant, Hairdresser, Hotel Attendant, Kitchen Helper, Landscaper, Lawyer, Librarian, Logger, Machinist, Mail Carrier, Massage Therapist, Medical Technician, Miner, Model Maker, Nurse, Operations Manager, Packager, Personal Care Specialist, Photographer, Physical Therapist, Pilot, Plumber, Police Officer, Porter, Producer, Production Worker, Rail Worker, Real Estate Broker, Religious Leader, Sailor, Salesperson, Scientist, Secretary, Security Guard, Social Worker, Software Developer, Soldier, Stock Clerk, Surveying Technician, Taxi Driver, Teacher, Technician, Truck Driver, Unemployed, Veterinarian, Waiter, Welder, Writer.
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

**1. A list of example people (easiest).** One row per person, one column per trait, for example `age, gender, race`. Optionally add a `weight` column for how common each kind of person is (leave it out to weight everyone equally). Save as CSV or Excel and point the module at it.

| age | gender | race | weight |
|---|---|---|---|
| 20-35 years old | female | asian | 5 |
| 20-35 years old | male | white | 2 |
| 36-50 years old | female | black | 3 |

Write each value the way it should read in the prompt (`20-35 years old`, not `20-35`), because it is inserted verbatim.

Different traits entirely — just change the columns. For example, matching a brand's own customer base:

| age | gender | region | weight |
|---|---|---|---|
| 20-35 years old | female | urban | 4 |
| 36-50 years old | male | suburban | 2 |
| 51-70 years old | female | rural | 1 |

→ `"a photo of a 20-35 years old, female, urban person shopping online"`

A whole row is sampled at a time, so any real correlations in your data are kept (and the proportions come out matching your table). You do not have to precompute anything, but if you want to see or export the resulting percentages as a census-style table, call `.to_percentages()`:

```python
DiversityModule("my_people.csv").to_percentages()   # -> group, attribute, value, pct
```

**2. Percentages.** If you know the shares but not individual people, provide them directly with columns `attribute, value, pct` (this is how the bundled census ships).

| attribute | value | pct |
|---|---|---|
| gender | female | 70 |
| gender | male | 30 |
| age | gen-z | 60 |
| age | millennial | 40 |

### Conditioning on a word in the prompt (like occupations)

Add a `group` column (or name it `occupation`) to give each group its own distribution. Its value is matched in the prompt, the matching subset is used, and the description is inserted before that word. This is exactly how the built-in occupations work. Example rows: `group=nurse, gender, female, 86` ... `group=ceo, gender, female, 29`. Leave the `group` column out and one distribution applies to every prompt. Add a `person` group as the fallback for prompts that name no group (the bundled census does this).

### What to watch out for

- **Values are inserted verbatim.** Control the wording through the value strings themselves (`"in their 30s"`, `"aged 25-34"`, `"young"`). Set the separator with `DiversityModule(..., sep=", ")`.
- **Column order = description order.** Reorder columns, or pass `attribute_order=["age", "race", "gender"]`.
- **Grouping needs a word in the prompt.** It only helps when the group value (e.g. an occupation) actually appears in your prompts. For "make everyone match my customers", skip the group column and use one distribution.
- **Weights are optional.** With example-people tables, no `weight` means every row is equally likely; with percentage tables, `pct` (or `weight`/`count`) sets the shares.
- Load from CSV or Excel by passing a DataFrame: `DiversityModule(pd.read_excel("my.xlsx"))`.

## Bundled dataset

`promptdiv/data/census.csv` is the long table used by default: columns `group` (84 occupations plus `person` for the whole population), `attribute` (age, race, gender), `value`, `pct`. It was built from person-level US Census microdata (IPUMS, 2020): sex, age (in seven bands), a four-class race label, and occupation, with the 462 detailed occupations grouped into 84 by weighted k-means on their demographic composition, then turned into person-weighted percentages. `promptdiv/data/occupation_mapping.csv` is the 462→84 crosswalk. Raw IPUMS microdata are not redistributed here (IPUMS licensing); the package ships the aggregated percentages.

## Evaluation

On FLUX.1-dev across the advertising corpus in the accompanying paper, the module cut the mean occupation-level distance to the population from 18.7 to 11.6 percentage points, and moved Black representation from 4.8% to 13.1% (population value 13.3%). In a preregistered experiment (N = 193), census-grounded ads were seen as more representative, moved gender stereotypes toward parity, were rated more appealing, and raised felt inclusion for under-represented viewers with no decrease for others.

Prompt augmentation can only realign what the model will actually draw. In our tests the generators did not render recognisably Hispanic faces even when asked, so requested Hispanic representation did not appear in the output. This is a limit of the underlying models, not of the prompt method.

## Citation

```bibtex
@article{jansen2026promptdiv,
  title   = {Census-grounded prompt augmentation reduces demographic misrepresentation in AI-generated advertising},
  author  = {Jansen, Tijmen},
  year    = {2026},
  note    = {Manuscript in preparation}
}
```

## License

MIT (see `LICENSE`). The bundled demographic summaries are derived from US Census microdata accessed via IPUMS; please acknowledge IPUMS when you use them.
