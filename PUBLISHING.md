# How to publish v0.2.0

The repository already exists at https://github.com/TijmenJansen0/prompt-div and
has a Zenodo DOI. **This is an update to it, not a new repository** — pushing to
the same repo is what keeps the DOI, the stars and the paper's citation valid.

v0.2.0 is a breaking release: the bundled distribution, the sampling method and
the output strings all changed. `CHANGELOG.md` says what and why.

---

## 1. Push the update

From inside this folder:

```bash
git init                                     # only if this copy has no .git yet
git remote add origin https://github.com/TijmenJansen0/prompt-div.git
git add -A
git commit -m "v0.2.0: joint person sampling, detailed census race, adults only"
git branch -M main
git push -u origin main
```

If the local copy has no history and the remote does, `git push --force-with-lease`
replaces it. That is fine here — the released versions live in the tags and on
Zenodo, not in the branch history.

## 2. Tag the release

On the repo page: **Releases → Draft a new release → Choose a tag →** type
`v0.2.0` → title `v0.2.0` → paste the top section of `CHANGELOG.md` as the
description → **Publish release**.

Zenodo is already watching the repository, so publishing the release mints a new
version DOI automatically. The concept DOI in the README
(10.5281/zenodo.21889100) keeps resolving to the latest, so it needs no edit.

## 3. Publish to PyPI

```bash
python -m pip install -U build twine
python -m build
twine check dist/*
twine upload dist/*
```

The wheel must contain `promptdiv/data/census.csv.gz` — check with
`python -c "import zipfile,glob; print(zipfile.ZipFile(glob.glob('dist/*.whl')[0]).namelist())"`
before uploading, because a wheel missing the data installs cleanly and then
fails on first use.

## 4. Verify a clean install

```bash
python -m venv /tmp/pdv && /tmp/pdv/bin/pip install -q promptdiv
/tmp/pdv/bin/python -c "
from promptdiv import apply_prompt_diversity as f
print(f('an ad for a nurse in a hospital'))
print(f('a photo of a person diving in the water'))"
```

Two sensible sentences with an age, a race and a gender in them means the
release works end to end: the download, the packaged data, and the sampling.

---

## Before you push — checklist

- [ ] `python examples/quickstart.py` and `python examples/own_dataset.py` both run.
- [ ] Version is `0.2.0` in **both** `pyproject.toml` and `promptdiv/__init__.py`.
- [ ] `promptdiv/data/census.csv` (the old four-class table) is **gone** — only
      `census.csv.gz` ships. Leaving the old file would make `DiversityModule()`
      silently load the superseded taxonomy.
- [ ] No raw microdata: the bundled table is aggregated weighted cell counts,
      which is the form IPUMS terms allow redistributing. `build_census.py` reads
      the microdata from the server and is not shipped in the wheel.
- [ ] README numbers match the current analysis — they were regenerated for this
      release and will go stale if the paper's numbers move again.
