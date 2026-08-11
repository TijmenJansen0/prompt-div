# How to put this on GitHub

The repository is this `prompt-div` folder. Everything needed is already here
(`README.md`, `LICENSE`, `pyproject.toml`, the `promptdiv/` package, `examples/`).
You do not need to add or edit anything to publish it.

Pick one of the two methods below. The website method needs no command line.

---

## Method A — GitHub website (no terminal)

1. Go to https://github.com and sign in (create a free account if you do not have one).
2. Top-right, click the **+** icon → **New repository**.
3. Fill in:
   - **Repository name:** `prompt-div`
   - **Description** (optional): "Census-grounded prompt augmentation for text-to-image models"
   - **Public**
   - Leave **"Add a README file", "Add .gitignore", "Choose a license" UNCHECKED** — you already have them.
4. Click **Create repository**.
5. On the new empty repository page, click the link **"uploading an existing file"** (in the "Quick setup" box), or go to **Add file → Upload files**.
6. Open this `prompt-div` folder on your computer, select **everything inside it** (the files *and* the `promptdiv` and `examples` folders — not the outer folder itself), and drag it onto the upload area. GitHub keeps the folder structure.
7. At the bottom, in **Commit changes**, type a message like `initial commit`, then click **Commit changes**.

Done — your code is live at `https://github.com/<your-username>/prompt-div`.

To confirm it installs:

```bash
pip install git+https://github.com/<your-username>/prompt-div
```

---

## Method B — command line (git)

From inside the `prompt-div` folder:

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
```

Create an empty repository on github.com first (steps 2–4 above, still unchecked
boxes), then copy its URL and:

```bash
git remote add origin https://github.com/<your-username>/prompt-div.git
git push -u origin main
```

---

## Optional next steps

**Tag a release (recommended before you cite it in the paper).**
On the repo page: **Releases → Create a new release → Choose a tag →** type `v0.1.0`
→ **Publish release**. This gives a fixed, citable snapshot.

**Get a DOI for the paper (Zenodo).**
Go to https://zenodo.org, sign in with GitHub, open **Settings → GitHub**, flip the
switch **On** next to `prompt-div`, then publish a release (step above). Zenodo mints
a DOI automatically. Put that DOI in the manuscript's Data & Code Availability
statement and in the README citation.

**Publish to PyPI so anyone can `pip install promptdiv`** (optional):

```bash
pip install build twine
python -m build
twine upload dist/*
```

You will need a free account at https://pypi.org. Before uploading, set a unique
`name` in `pyproject.toml` if `promptdiv` is already taken, and bump `version` for
each release.

---

## Before you push — quick checklist

- `pyproject.toml` — set `authors` and the `Homepage`/`Repository` URLs to your username.
- `README.md` citation block — add the final title/DOI when known.
- Nothing secret is included (there is a `.gitignore`; the bundled data is only
  aggregated census percentages, no raw microdata).
