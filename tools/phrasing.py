"""How a sampled census demographic becomes prompt text.

Kept in its own module because the mixed-race phrasing is an empirical question,
not a style choice: asking FLUX for "a Black and Japanese construction worker"
reads as a LIST and reliably produces two people, one of each. Binding the two
origins to a single subject needs a post-modifier after the noun. The candidate
phrasings below are pilot-tested before one is adopted.
"""
import re

# ---- descriptor construction ------------------------------------------------
SINGLE = {  # RACED label prefix -> adjective
    "White": "White", "Black/African American": "Black",
    "Chinese": "Chinese", "Japanese": "Japanese", "Filipino": "Filipino",
    "Korean": "Korean", "Vietnamese": "Vietnamese",
    "Asian Indian": "Indian", "Cambodian": "Cambodian", "Hmong": "Hmong",
    "Laotian": "Laotian", "Thai": "Thai", "Bangladeshi": "Bangladeshi",
    "Pakistani": "Pakistani", "Sri Lankan": "Sri Lankan", "Nepalese": "Nepalese",
    "Indonesian": "Indonesian", "Taiwanese": "Taiwanese", "Burmese": "Burmese",
    "Bhutanese": "Bhutanese", "Mongolian": "Mongolian", "Malaysian": "Malaysian",
    "Native Hawaiian": "Native Hawaiian", "Hawaiian": "Native Hawaiian",
    "Samoan": "Samoan", "Tongan": "Tongan", "Chamorro": "Chamorro",
    "Guamanian": "Chamorro", "Fijian": "Fijian", "Marshallese": "Marshallese",
}
TRIBES = ["Navajo","Cherokee","Sioux","Chippewa","Choctaw","Apache","Lumbee",
          "Pueblo","Creek","Iroquois","Yup'ik","Inupiat","Pima","Chickasaw",
          "Blackfoot","Yaqui","Hopi","Tohono O Odham","Potawatomi",
          "Puget Sound Salish","Alaskan Athabaskan","Crow","Aleut","Cheyenne",
          "Tlingit","Comanche"]
HISPANIC = {  # HISPAND label prefix -> nationality adjective
    "Mexican":"Mexican","Puerto Rican":"Puerto Rican","Cuban":"Cuban",
    "Dominican":"Dominican","Salvadoran":"Salvadoran","Guatemalan":"Guatemalan",
    "Colombian":"Colombian","Honduran":"Honduran","Ecuadorian":"Ecuadorian",
    "Peruvian":"Peruvian","Nicaraguan":"Nicaraguan","Venezuelan":"Venezuelan",
    "Argentinean":"Argentinian","Chilean":"Chilean","Costa Rican":"Costa Rican",
    "Panamanian":"Panamanian","Bolivian":"Bolivian","Uruguayan":"Uruguayan",
    "Paraguayan":"Paraguayan","Spaniard":"Spanish",
}
# two-race combinations we can name; order preserved from the census label
PAIR = re.compile(r"^(White|Black|Chinese|Japanese|Filipino|Korean|Vietnamese|"
                  r"Asian Indian|AIAN|Native Hawaiian|Samoan|Chamorro|Taiwanese|Hawaiian)"
                  r" and (White|Black|Chinese|Japanese|Filipino|Korean|Vietnamese|"
                  r"Asian Indian|AIAN|Native Hawaiian|Samoan|Chamorro|Taiwanese|Hawaiian)$")
NAME = {"AIAN": "Native American", "Asian Indian": "Indian",
        "Black": "Black", "Hawaiian": "Native Hawaiian"}


UNINFORMATIVE = ("white", "other race", "write_in", "two major", "three or more",
                 "n.e.c.", "not specified", "tribe not specified")
SPANISH_ORIGIN_TRIBES = ("mexican american indian", "south american indian",
                         "central american indian")   # lowercase: matched against low

def _hispanic_name(hispand):
    if isinstance(hispand, str):
        for k, v in HISPANIC.items():
            if hispand.startswith(k):
                return v
    return "Hispanic"

def classify(raced, hispand, hispan):
    """-> (kind, value). kind is 'single' | 'pair' | 'generic'.

    Hispanic origin normally decides the descriptor, because a Hispanic
    respondent's RACED is usually "White" or "Other race, n.e.c." and using the
    race alone would erase the largest US minority. But it must NOT override a
    race that already names something renderable: a Hispanic Navajo respondent
    should still be asked for as Navajo, not flattened to "Hispanic". So the
    override applies only when RACED itself carries no detail.
    """
    hisp = bool(hispan and hispan != 0)
    low = raced.lower() if isinstance(raced, str) else ""
    if hisp and any(t in low for t in SPANISH_ORIGIN_TRIBES):
        return "single", _hispanic_name(hispand)
    if hisp and (not low or any(u in low for u in UNINFORMATIVE)):
        return "single", _hispanic_name(hispand)
    if not isinstance(raced, str):
        return "single", "White"
    for t in TRIBES:
        if raced.startswith(t):
            return "single", t.replace(" O Odham", " O'odham")
    m = PAIR.match(raced.strip())
    if m:
        a, b = (NAME.get(x, x) for x in m.groups())
        return "pair", (a, b)
    for k, v in SINGLE.items():
        if raced.startswith(k):
            return "single", v
    low = raced.lower()
    if "american indian" in low or "alaska native" in low or "tribe" in low:
        return "single", "Native American"
    if "other asian" in low:
        return "single", "Asian"
    if "pacific islander" in low or low.startswith("pi "):
        return "single", "Pacific Islander"
    return "generic", "multiracial"                 # 3+ races, write_in combos


# ---- phrasing variants (pilot-tested) ---------------------------------------
def _art(w):
    return "an" if w[0].lower() in "aeiou" else "a"

PHRASINGS = {
    # adjective list -- the KNOWN-BAD control, included so the pilot shows the failure
    "list":      lambda a, b: ("adj", f"{a} and {b}"),
    "heritage":  lambda a, b: ("post", f"of mixed {a} and {b} heritage"),
    "descent":   lambda a, b: ("post", f"of mixed {a} and {b} descent"),
    "biracial":  lambda a, b: ("post", f"who is biracial, with {a} and {b} heritage"),
}


def build_prompt(base_prompt, age, gender, kind, value, phrasing="heritage",
                 subject=None):
    """Insert age, gender and race into the prompt's subject.

    Single race becomes an adjective: 'a 38-year-old Black male construction worker'.
    A pair becomes a post-modifier so both origins bind to ONE subject:
    'a 38-year-old male construction worker of mixed Black and Japanese heritage'.
    """
    age_g = f"{int(round(age))}-year-old"
    if kind == "pair":
        slot, text = PHRASINGS[phrasing](*value)
        lead = f"{age_g} {text} {gender}" if slot == "adj" else f"{age_g} {gender}"
        post = "" if slot == "adj" else f" {text}"
    else:
        lead, post = f"{age_g} {value} {gender}", ""

    art = _art(lead)
    # "a realistic photo of a construction worker ..." -> insert before the noun
    m = re.match(r'^(\s*a realistic photo of\s+)(an?|the)\s+(.*)$', base_prompt,
                 flags=re.I | re.S)
    if not m:
        return None
    head, rest = m.group(1), m.group(3)
    if post:
        # Anchor the modifier to the SUBJECT NOUN itself. Guessing the noun phrase
        # with a stop-word regex put it after adverbs ("a CEO indoors of mixed
        # Black and Filipino heritage in an office"), which reads as nonsense and
        # detaches the ask from the person.
        cut = None
        if subject:
            m2 = re.match(rf'^\s*{re.escape(subject)}\b', rest, flags=re.I)
            if m2:
                cut = m2.end()
        if cut is None:
            m2 = re.match(r'^\s*(?:person|man|woman|worker|[A-Za-z]+(?:\s+[a-z]+){0,2}?)\b',
                          rest, flags=re.I)
            cut = m2.end() if m2 else None
        rest = (rest[:cut] + post + rest[cut:]) if cut else (rest.rstrip(". ") + post + ".")
    return f"{head}{art} {lead} {rest}"
