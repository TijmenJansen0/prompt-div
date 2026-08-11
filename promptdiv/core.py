"""
promptdiv.core
==============
Census-grounded prompt augmentation for text-to-image models.

Before an image is generated the prompt is rewritten to describe a person
sampled from a demographic distribution. The distribution is just a table, and
the module does not hard-code what the attributes are: age, race and gender in
the bundled US Census data, but equally sexuality, customer segment, region, or
anything else in your own table.

Two table shapes are accepted, both auto-detected:

* long  - columns ``group, attribute, value, pct`` (one row per value share).
          This is how the bundled census ships and the easiest to hand-write.
* wide  - one row per example person, one column per attribute (+ optional
          ``weight``). A whole row is sampled, so real correlations are kept.

``group`` is optional. If present, its value is matched in the prompt (e.g. an
occupation) and the distribution for that group is used; otherwise a single
distribution applies to every prompt.
"""
from __future__ import annotations
import os
import re
from functools import lru_cache
import numpy as np
import pandas as pd

_CENSUS = os.path.join(os.path.dirname(__file__), "data", "census.csv")


class DiversityModule:
    """
    Parameters
    ----------
    data : str or pandas.DataFrame, optional
        A distribution table (long or wide, see module docstring). Defaults to
        the bundled US Census table.
    group_column : str, optional
        Name of the column whose value is matched in the prompt. Auto-detected
        as ``group`` or ``occupation`` if not given. Pass ``None`` data with no
        such column for a single, ungrouped distribution.
    attribute_order : list of str, optional
        Order in which attributes are written into the descriptor. Defaults to
        the order they appear in the table.
    seed : int, optional
    sep : str
        Separator between attribute values in the descriptor (default ``", "``).
    """

    def __init__(self, data=None, group_column=None, attribute_order=None,
                 seed=None, sep=", "):
        self.rng = np.random.default_rng(seed)
        self.sep = sep

        df = data if isinstance(data, pd.DataFrame) else pd.read_csv(_CENSUS if data is None else data)
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        lower = {c.lower(): c for c in df.columns}

        gcol = group_column or next((lower[k] for k in ("group", "occupation") if k in lower), None)
        groups = (df[gcol].astype(str).str.lower().str.strip() if gcol else pd.Series(["person"] * len(df)))

        if "attribute" in lower and "value" in lower:               # long format
            self.mode = "long"
            acol, vcol = lower["attribute"], lower["value"]
            wcol = next((lower[k] for k in ("pct", "percent", "percentage", "weight", "count", "n") if k in lower), None)
            df["_w"] = df[wcol].astype(float) if wcol else 1.0
            df["_g"] = groups
            self.attrs = list(dict.fromkeys(df[acol].astype(str)))   # order of appearance
            self._dist = {}
            for g, gd in df.groupby("_g"):
                self._dist[g] = {}
                for a, ad in gd.groupby(acol):
                    w = ad["_w"].to_numpy(float)
                    self._dist[g][str(a)] = (ad[vcol].astype(str).tolist(), w / w.sum())
        else:                                                        # wide records
            self.mode = "records"
            wcol = next((lower[k] for k in ("weight", "count", "n") if k in lower), None)
            self.attrs = [c for c in df.columns if c not in (gcol, wcol)]
            df["_w"] = df[wcol].astype(float) if wcol else 1.0
            df["_g"] = groups
            self._rows = {g: gd.reset_index(drop=True) for g, gd in df.groupby("_g")}

        if attribute_order:
            self.attrs = list(attribute_order)
        keys = self._dist if self.mode == "long" else self._rows
        self._default = next((g for g in ("person", "total", "all") if g in keys), next(iter(keys)))
        # groups matched inside a prompt: real names only (not the generic fallback)
        self.groups = sorted([g for g in keys if g not in ("person", "total", "all")],
                            key=len, reverse=True)

    # -- sampling -----------------------------------------------------------
    def sample(self, group=None) -> dict:
        """Return one sampled ``{attribute: value}`` for a group (or the default distribution)."""
        g = (group or "").lower().strip()
        if self.mode == "long":
            d = self._dist.get(g, self._dist[self._default])
            return {a: str(self.rng.choice(v, p=p)) for a, (v, p) in d.items()}
        gd = self._rows.get(g, self._rows[self._default])
        row = gd.sample(1, weights=gd["_w"], random_state=int(self.rng.integers(1_000_000_000))).iloc[0]
        return {a: str(row[a]) for a in self.attrs}

    def descriptor(self, group=None) -> str:
        s = self.sample(group)
        return self.sep.join(s[a] for a in self.attrs if a in s)

    def to_percentages(self) -> pd.DataFrame:
        """Return the distribution as a long ``group, attribute, value, pct`` table.

        Useful to see or export the percentages computed from an example-people
        table (the same shape as the bundled census)."""
        rows = []
        if self.mode == "long":
            for g, d in self._dist.items():
                for a, (vals, probs) in d.items():
                    for v, p in zip(vals, probs):
                        rows.append((g, a, v, round(float(p) * 100, 2)))
        else:
            for g, gd in self._rows.items():
                for a in self.attrs:
                    w = gd.groupby(a)["_w"].sum()
                    w = w / w.sum() * 100
                    for v, p in w.items():
                        rows.append((g, a, str(v), round(float(p), 2)))
        return pd.DataFrame(rows, columns=["group", "attribute", "value", "pct"])

    # -- prompt augmentation -----------------------------------------------
    def _find_group(self, prompt):
        low = prompt.lower()
        for g in self.groups:                      # longest name first
            m = re.search(r"\b" + re.escape(g) + r"\b", low)
            if m:
                return g, m.start(), m.end()
        return None

    def augment(self, prompt: str, active: bool = True, group=None) -> str:
        """
        Rewrite ``prompt`` with a sampled descriptor. The group (e.g. occupation)
        is detected from the prompt unless you pass ``group``. ``active=False``
        returns the prompt unchanged.
        """
        if not active:
            return prompt

        if group is None:
            hit = self._find_group(prompt)
            if hit:
                g, s, e = hit
                return prompt[:s] + f"{self.descriptor(g)} {prompt[s:e]}" + prompt[e:]
            desc = self.descriptor()
            m = re.search(r"\bperson\b", prompt, re.IGNORECASE)
            if m:
                return prompt[:m.start()] + f"{desc} {prompt[m.start():m.end()]}" + prompt[m.end():]
            return f"a {desc} person. " + prompt

        desc = self.descriptor(group)
        m = re.search(r"\b" + re.escape(group) + r"\b", prompt, re.IGNORECASE)
        if m:
            return prompt[:m.start()] + f"{desc} {prompt[m.start():m.end()]}" + prompt[m.end():]
        return f"a {desc} {group}. " + prompt


# -- convenience --------------------------------------------------------------
@lru_cache(maxsize=1)
def _default_module():
    return DiversityModule()


def apply_prompt_diversity(prompt: str, active: bool = True, group=None) -> str:
    """Rewrite a prompt using the bundled US Census distribution."""
    return _default_module().augment(prompt, active=active, group=group)


def enable_diversity(pipe, module=None, default: bool = False):
    """
    Wrap a text-to-image pipeline so its call accepts ``apply_prompt_diversity=True``:

    >>> pipe = enable_diversity(pipe)
    >>> img = pipe(prompt="a photo of a person in an office",
    ...            apply_prompt_diversity=True, num_inference_steps=30).images[0]
    """
    mod = module or _default_module()

    class _DiversePipe:
        def __init__(self, inner):
            object.__setattr__(self, "_inner", inner)

        def _aug(self, p):
            return type(p)(mod.augment(x, True) for x in p) if isinstance(p, (list, tuple)) else mod.augment(p, True)

        def __call__(self, *args, apply_prompt_diversity=default, **kwargs):
            if apply_prompt_diversity:
                if kwargs.get("prompt") is not None:
                    kwargs["prompt"] = self._aug(kwargs["prompt"])
                elif args and isinstance(args[0], (str, list, tuple)):
                    args = (self._aug(args[0]),) + args[1:]
            return self._inner(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, "_inner"), name)

    return _DiversePipe(pipe)
