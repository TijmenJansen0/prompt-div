"""
promptdiv.core
==============
Census-grounded prompt augmentation for text-to-image models.

Before an image is generated the prompt is rewritten to describe a person drawn
from a demographic distribution. The distribution is just a table, and the
module does not hard-code what the attributes are: age, race and gender in the
bundled US Census data, but equally sexuality, customer segment, region, or
anything else in your own table.

Two table shapes are accepted, both auto-detected:

* people - one row per kind of person, one column per attribute, plus an
           optional ``weight``. A whole row is drawn at a time, so the real
           correlations between attributes survive. This is how the bundled
           census ships and it is what the paper evaluates.
* shares - columns ``group, attribute, value, pct``, one row per value share.
           Easier to hand-write, but each attribute is drawn independently, so
           any correlation between them is lost.

``group`` is optional. If present, its value is matched in the prompt (e.g. an
occupation) and that group's distribution is used; otherwise a single
distribution applies to every prompt.

A ``post`` column, if present, holds text that belongs *after* the subject noun
rather than before it. The bundled census uses it for mixed-race people:
"a Black and Japanese construction worker" reads as a list and makes generators
draw two people, one of each, whereas "a construction worker of mixed Black and
Japanese heritage" binds both origins to one person.
"""
from __future__ import annotations
import os
import re
from functools import lru_cache
import numpy as np
import pandas as pd

_CENSUS = os.path.join(os.path.dirname(__file__), "data", "census.csv.gz")

_GROUP_COLS = ("group", "occupation")
_WEIGHT_COLS = ("weight", "pct", "percent", "percentage", "count", "n")
_POST_COL = "post"


def _art(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _as_text(attr: str, value) -> str:
    """Render one attribute value as it should read inside a prompt.

    Numeric ages are the only special case: the table stores 34, the prompt
    needs "34-year-old". Everything else is inserted exactly as written, which
    is what lets a user's own table say "in their 30s" or "urban".
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    if attr == "age" and isinstance(value, (int, np.integer)):
        return f"{int(value)}-year-old"
    if attr == "age" and isinstance(value, (float, np.floating)):
        return f"{int(round(value))}-year-old"
    return str(value).strip()


class _Pool:
    """One group's people, prepared for exact weighted draws.

    The cumulative weight is built once and sampled by binary search, so a run
    of a thousand prompts costs one vectorised lookup rather than a thousand
    trips through pandas.
    """

    def __init__(self, frame: pd.DataFrame, attrs, weight_col, post_col):
        self.attrs = attrs
        self.cols = {a: frame[a].to_numpy(dtype=object) for a in attrs}
        self.post = (frame[post_col].to_numpy(dtype=object)
                     if post_col in frame.columns else None)
        w = (frame[weight_col].to_numpy(dtype=float) if weight_col
             else np.ones(len(frame)))
        w = np.clip(np.nan_to_num(w, nan=0.0), 0, None)
        self.cum = np.cumsum(w)
        self.total = float(self.cum[-1])

    def draw(self, rng) -> int:
        i = int(np.searchsorted(self.cum, rng.random() * self.total))
        return min(i, len(self.cum) - 1)


class DiversityModule:
    """
    Parameters
    ----------
    data : str or pandas.DataFrame, optional
        A distribution table (people or shares, see module docstring). Defaults
        to the bundled US Census table.
    group_column : str, optional
        Name of the column whose value is matched in the prompt. Auto-detected
        as ``group`` or ``occupation`` if not given.
    attribute_order : list of str, optional
        Order in which attributes are written into the descriptor. Defaults to
        the order they appear in the table.
    seed : int, optional
        Fixes the draws, for reproducible runs.
    sep : str
        Separator between attribute values (default a single space, which reads
        naturally for the bundled census: "a 34-year-old Filipino female nurse").
        Pass ``", "`` for comma-separated descriptors.
    """

    def __init__(self, data=None, group_column=None, attribute_order=None,
                 seed=None, sep=" "):
        self.rng = np.random.default_rng(seed)
        self.sep = sep

        if isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            df = pd.read_csv(_CENSUS if data is None else data)
        df.columns = [str(c).strip() for c in df.columns]
        lower = {c.lower(): c for c in df.columns}

        gcol = group_column or next((lower[k] for k in _GROUP_COLS if k in lower), None)
        groups = (df[gcol].astype(str).str.lower().str.strip() if gcol
                  else pd.Series(["person"] * len(df), index=df.index))
        df["_g"] = groups

        if "attribute" in lower and "value" in lower:
            self.mode = "shares"
            self._build_shares(df, lower)
        else:
            self.mode = "people"
            self._build_people(df, lower, gcol)

        if attribute_order:
            self.attrs = [a for a in attribute_order if a in self.attrs]

        keys = self._dist if self.mode == "shares" else self._pools
        self._default = next((g for g in ("person", "total", "all") if g in keys),
                             next(iter(keys)))
        # Names matched inside a prompt; the generic fallback is not one of them.
        self.groups = sorted([g for g in keys if g not in ("person", "total", "all")],
                             key=len, reverse=True)

    # -- table shapes -------------------------------------------------------
    def _build_people(self, df, lower, gcol):
        wcol = next((lower[k] for k in _WEIGHT_COLS if k in lower), None)
        self.post_col = lower.get(_POST_COL)
        reserved = {gcol, wcol, self.post_col, "_g"}
        self.attrs = [c for c in df.columns if c not in reserved]
        self._pools = {g: _Pool(sub, self.attrs, wcol, self.post_col or "")
                       for g, sub in df.groupby("_g")}

    def _build_shares(self, df, lower):
        acol, vcol = lower["attribute"], lower["value"]
        wcol = next((lower[k] for k in _WEIGHT_COLS if k in lower), None)
        self.post_col = None
        df["_w"] = df[wcol].astype(float) if wcol else 1.0
        self.attrs = list(dict.fromkeys(df[acol].astype(str)))
        self._dist = {}
        for g, gd in df.groupby("_g"):
            self._dist[g] = {}
            for a, ad in gd.groupby(acol):
                w = ad["_w"].to_numpy(float)
                self._dist[g][str(a)] = (ad[vcol].astype(str).tolist(), w / w.sum())

    # -- sampling -----------------------------------------------------------
    def sample(self, group=None) -> dict:
        """Draw one person as ``{attribute: value}`` from a group's distribution.

        In ``people`` mode a whole row is drawn, so the attributes come out
        correlated the way they are in the table. A ``post`` value, where the
        table has one, is returned under the key ``"post"``.
        """
        g = (group or "").lower().strip()
        if self.mode == "shares":
            d = self._dist.get(g, self._dist[self._default])
            return {a: str(self.rng.choice(v, p=p)) for a, (v, p) in d.items()}

        pool = self._pools.get(g, self._pools[self._default])
        i = pool.draw(self.rng)
        out = {a: pool.cols[a][i] for a in self.attrs}
        if pool.post is not None:
            out["post"] = pool.post[i]
        return out

    def descriptor(self, group=None):
        """Return ``(before, after)`` text for one sampled person.

        ``before`` goes in front of the subject noun, ``after`` behind it.
        """
        s = self.sample(group)
        before = self.sep.join(t for a in self.attrs
                               if (t := _as_text(a, s.get(a))))
        after = _as_text("post", s.get("post"))
        return before, after

    def to_percentages(self) -> pd.DataFrame:
        """The distribution as a long ``group, attribute, value, pct`` table.

        Useful to see or export the shares implied by a table of people.
        """
        rows = []
        if self.mode == "shares":
            for g, d in self._dist.items():
                for a, (vals, probs) in d.items():
                    rows += [(g, a, v, round(float(p) * 100, 2)) for v, p in zip(vals, probs)]
        else:
            for g, pool in self._pools.items():
                w = pd.Series(np.diff(pool.cum, prepend=0.0))
                cols = dict(pool.attrs and {a: pool.cols[a] for a in self.attrs})
                if pool.post is not None:
                    cols["post"] = pool.post
                for a, values in cols.items():
                    # Blanks are a real category here -- a mixed-race person has
                    # no single race value -- so they are counted, not dropped.
                    keys = pd.Series([_as_text(a, v) for v in values])
                    s = w.groupby(keys).sum()
                    s = s / s.sum() * 100
                    rows += [(g, a, str(v), round(float(q), 2)) for v, q in s.items()]
        return pd.DataFrame(rows, columns=["group", "attribute", "value", "pct"])

    # -- prompt augmentation -------------------------------------------------
    def _find_group(self, prompt):
        low = prompt.lower()
        for g in self.groups:                       # longest name first
            m = re.search(r"\b" + re.escape(g) + r"\b", low)
            if m:
                return g, m.start(), m.end()
        return None

    def _insert(self, prompt, start, end, before, after):
        head = f"{before} " if before else ""
        tail = f" {after}" if after else ""
        return prompt[:start] + head + prompt[start:end] + tail + prompt[end:]

    def augment(self, prompt: str, active: bool = True, group=None) -> str:
        """
        Rewrite ``prompt`` to describe a sampled person. The group (e.g. an
        occupation) is detected from the prompt unless you pass ``group``.
        ``active=False`` returns the prompt unchanged.
        """
        if not active:
            return prompt

        if group is None:
            hit = self._find_group(prompt)
            if hit:
                g, s, e = hit
                return self._insert(prompt, s, e, *self.descriptor(g))
            before, after = self.descriptor()
            m = re.search(r"\bperson\b", prompt, re.IGNORECASE)
            if m:
                return self._insert(prompt, m.start(), m.end(), before, after)
        else:
            before, after = self.descriptor(group)
            m = re.search(r"\b" + re.escape(group) + r"\b", prompt, re.IGNORECASE)
            if m:
                return self._insert(prompt, m.start(), m.end(), before, after)

        noun = group or "person"
        tail = f" {after}" if after else ""
        lead = before or noun
        return f"{_art(lead)} {before + ' ' if before else ''}{noun}{tail}. {prompt}"


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
            return (type(p)(mod.augment(x, True) for x in p)
                    if isinstance(p, (list, tuple)) else mod.augment(p, True))

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
