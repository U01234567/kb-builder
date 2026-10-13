# kb-builder

Builds question–answer knowledge bases for chatbots from your own source documents, with a local
language model. Every answer cites the passages it rests on, and a person reviews every answer
before it is used.

You write questions in an Excel file and put sources (PDF, saved web pages) in a folder. kb-builder
finds the passages that carry each answer, lets the model judge them, writes an answer, a simpler
version and extra phrasings of the question, and checks that every quote really is in its source.
A reviewer then accepts, rejects or edits each answer in a small app in the browser. Everything ends
up in the same Excel file.

## Two computers, three commands

| Where | Command | What it does |
|---|---|---|
| GPU server, terminal | `python manage.py preflight` | Checks `kb.xlsx` and `materials/`; changes nothing |
| GPU server, terminal | `python manage.py generate` | Preflight, then answers the questions with Ollama on the GPUs |
| Your laptop, browser | `python manage.py review` | Opens the review app on `127.0.0.1` |

Only `project/project.toml` and `project/kb.xlsx` travel between the two, copied in whatever way you
normally move files. The laptop does not need the sources: the Evidence sheet holds every quote.

## Getting started

The start scripts are built around our university's setup: a shared Linux server with NVIDIA GPUs,
without administrator rights, for generating; Windows and macOS laptops for reviewing. Feel free to
adapt them to yours. kb-builder itself only needs Python 3.12 or newer, the packages in
`requirements.txt` and, for generating, [Ollama](https://ollama.com).

**On the GPU server**

1. Make sure Python 3.12 or newer and Git are available. Without administrator rights, Miniforge in
   your home folder works.
2. Clone this repository and `cd` into it.
3. `bash start_kb-builder_Linux.sh`. It creates `.venv`, installs `requirements.txt`, creates
   `/project/` from `/project-example/`, and puts the pinned Ollama release in `tools/ollama/`.
4. Put your sources in `project/materials/<folder>/` and your questions in `project/kb.xlsx`.
5. `.venv/bin/python manage.py preflight`, then `.venv/bin/python manage.py generate`.

Long runs keep going after you log out with:

```bash
nohup .venv/bin/python manage.py generate --mode missing --yes > generate.log 2>&1 &
```

**On a laptop**

Clone the repository (or unpack a ZIP of it) into an empty folder and double-click
`start_kb-builder_Windows.bat` (Windows) or `start_kb-builder_Mac.command` (macOS). It sets up `.venv`
and offers to open the review app. Put the project's `project.toml` and `kb.xlsx` in `project/` first.

## The project folder

Everything specific to one project lives in `/project/`, which is never committed. See
`project-example/README.md`. In `kb.xlsx`, each topic is a sheet with a `Question` column; the
**Topics** sheet says which folders of `materials/` each topic reads (`*` for all). kb-builder adds
the sheets Overview, Evidence, Sources and Runs, and keeps derived columns (grey headers) up to date.

## Updates and versions

The start scripts check GitHub and ask before updating; `/project/` is never touched. Every package in
`requirements.txt` may only move to a newer patch version (`~=X.Y.0`). Ollama and the models are
pinned in `scripts/start.py` and `project/project.toml`.

## More

- `docs/operations.md`: running, moving `kb.xlsx`, backups, handing over.
- `docs/decisions.md`: why kb-builder works the way it does.
- Tests: `python manage.py test` (no GPU or model needed).
