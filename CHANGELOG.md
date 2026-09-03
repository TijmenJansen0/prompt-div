# Changelog

## 0.2.0

The bundled distribution and the way it is sampled both changed. Output strings
differ from 0.1.0, so this is a breaking release.

**A whole person is now drawn at a time.** 0.1.0 sampled age, race and gender
independently from three marginal distributions. That reproduces the right
overall percentages and the wrong people: it erases the fact that nurses skew
female and CEOs skew older and Whiter. The bundled table is now one row per
distinct kind of adult with that kind's census weight, and a row is drawn whole.
This is the method the accompanying paper evaluates; 0.1.0 was not.

**Race is asked for in detail.** 0.1.0 shipped four values — `white`, `black`,
`asian`, `hispanic`. The distribution now carries the census's own detailed
codes: 78 single-race descriptors (Filipino, Navajo, Mexican, Vietnamese,
Samoan, ...) and 26 mixed-race phrasings. Coarse buckets flatten exactly the
minorities the tool exists to include, and `hispanic` as a race conflated
origin with appearance.

**Mixed-race people get a post-modifier.** `"a Black and Japanese construction
worker"` reads to a generator as a list and reliably produces two people, one of
each. A pair of origins is now written after the noun instead: `"a construction
worker of mixed Black and Japanese heritage"`. Tables may use the new `post`
column for any text that belongs after the subject.

**Adults only.** The age bands `0-16` and `16-24` are gone; ages are single
years, 18 and up. The paper measures adults, and a tool that rewrites prompts
for image generators should not be asking them to render children.

**Faster.** Draws are made by binary search over a precomputed cumulative
weight instead of a `DataFrame.sample` per prompt — about 3 µs per draw, so
batch generation is no longer bottlenecked on the module.

Also in this release:

- Descriptors default to space separation (`"a 34-year-old Filipino female
  nurse"`); pass `sep=", "` for the old comma style.
- `to_percentages()` no longer silently drops rows whose value is blank.
- The bundled table ships gzipped (`census.csv.gz`, under 1 MB).
- `build_census.py` in the repository root regenerates the table from the
  microdata, so the bundled file can be audited.
- 85 built-in occupations (was 84).

## 0.1.0

First release.
