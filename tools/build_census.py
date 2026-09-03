"""Rebuild `promptdiv/data/census.csv.gz` from IPUMS microdata.

Not part of the installed package, and not runnable from a clone alone: IPUMS
terms do not allow redistributing the microdata, so you need your own extract
(ACS person records with PERWT, SEX, AGE, RACED, HISPAN/HISPAND and OCC2010).
Set IPUMS_BASE to point at it. `phrasing.py` beside this file is the descriptor
logic the paper uses, so the derivation itself is fully readable here.

WHAT COMES OUT
  One row per distinct kind of adult, per occupation, with that kind's summed
  person-weight. Sampling a whole row therefore draws a real respondent's age,
  race and gender *together*, which is the point: nurses skew female, CEOs skew
  older and Whiter, and drawing the three independently would erase exactly the
  structure the module exists to reproduce.

  Collapsing identical people into weighted cells makes the table exact (no
  sampling error) and small, and keeps it an aggregate statistic rather than
  redistributed microdata, which is what the IPUMS terms allow.

  Adults only. The paper measures adults, and a tool that rewrites prompts for
  image generators should not be asking them to render children.
"""
import os, re, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from phrasing import classify, PHRASINGS          # the paper's own descriptor logic

# The IPUMS extract is not redistributable, so this points at wherever you keep
# yours. Everything else the script needs is in this directory.
B = os.environ.get("IPUMS_BASE", "/media/my_drives/DATA4/tijmen/AI_Biases")
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "promptdiv", "data", "census.csv.gz")
MAP_OUT = os.path.join(ROOT, "promptdiv", "data", "occupation_mapping.csv")
PHRASING = "heritage"                              # the pilot-selected mixed-race wording

ip = pd.read_csv(f"{B}/09_create_full_final_datasets/ipums_person_raced.csv")
ip = ip[ip.AGE >= 18].copy()

occmap = pd.read_csv(f"{B}/06_classify_occupations/01_create_mapping/occupation_mapping_final.csv")
raw = open(f"{B}/03_IPUMS_data/01_raw_IPUMS_data/usa_00004.xml").read()
var = re.search(r'<var ID="OCC2010".*?</var>', raw, re.S).group(0)
occ_label = {int(a): b.strip() for a, b in
             re.findall(r'<catgry>\s*<catValu>(\d+)</catValu>\s*<labl>([^<]*)</labl>', var)}
to_group = dict(zip(occmap.occupation, occmap.final_name))
ip["group"] = ip.OCC2010.map(occ_label).map(to_group)

# Resolve the race descriptor once per distinct (RACED, HISPAND, HISPAN), not per row.
key = ip[["raced_label", "hispand_label", "HISPAN"]].drop_duplicates()
key["kv"] = [classify(r, h, s) for r, h, s in zip(key.raced_label, key.hispand_label, key.HISPAN)]
ip = ip.merge(key, on=["raced_label", "hispand_label", "HISPAN"], how="left")

# A single race is an adjective before the noun. A pair has to become a
# post-modifier after it: "a Black and Japanese construction worker" reads as a
# list and makes the generator draw two people, one of each.
def split(kv):
    kind, value = kv
    if kind == "pair":
        slot, text = PHRASINGS[PHRASING](*value)
        return "", text
    return value, ""

ip[["race", "post"]] = pd.DataFrame([split(kv) for kv in ip.kv], index=ip.index)

CELL = ["age", "race", "gender", "post"]
ip = ip.rename(columns={"AGE": "age"})

def cells(frame, group):
    t = (frame.groupby(CELL, observed=True, dropna=False).PERWT.sum()
              .reset_index().rename(columns={"PERWT": "weight"}))
    t.insert(0, "group", group)
    t["weight"] = t.weight.round(0).astype("int64")
    return t[t.weight > 0]

parts = [cells(ip, "person")]                      # fallback: the whole adult population
for g, sub in ip.dropna(subset=["group"]).groupby("group"):
    if len(sub) > 30:                              # too few respondents to describe a group
        parts.append(cells(sub, g))

out = pd.concat(parts, ignore_index=True)
out = out.sort_values(["group", "age", "race", "gender"]).reset_index(drop=True)
out["age"] = out.age.astype(int)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
out.to_csv(OUT, index=False, compression="gzip")

occmap[["occupation", "final_name"]].rename(columns={"final_name": "group"}).to_csv(MAP_OUT, index=False)

print(f"wrote {OUT}")
print(f"  {len(out):,} rows | {out.group.nunique() - 1} occupations + 'person'"
      f" | {os.path.getsize(OUT)/1e6:.1f} MB")
print(f"  {out[out.post == ''].race.nunique()} single-race descriptors,"
      f" {out[out.post != ''].post.nunique()} mixed-race phrasings")
tot = out[out.group == "person"]
w = tot.weight / tot.weight.sum() * 100
print(f"  adult population check: female {w[tot.gender.values == 'female'].sum():.1f}%"
      f" | mean age {(tot.age * tot.weight).sum() / tot.weight.sum():.1f}")
