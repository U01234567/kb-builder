# Operations

## A run on the GPU server

1. Open a terminal in the `kb-builder` folder on the server.
2. Check that the GPUs are free: `nvidia-smi`. `generate` also checks and stops when they are busy.
3. `.venv/bin/python manage.py preflight`. Lines with **x** stop a run; lines with **!** are warnings.
   When the preflight can guess a fix (a renamed topic or folder, a typo), it offers it with [y]/[n].
4. `.venv/bin/python manage.py generate`. It shows the preflight, asks whether the Topics sheet is
   right, and asks what to run:
   - **Only questions without a generated answer**: new questions, and questions whose text changed.
   - **Full run again for chosen topics**: first a copy of `kb.xlsx` in `project/backups/`, then new
     answers; their reviews are cleared (the backup keeps the old ones).
5. For long runs, use `nohup` with `--mode` and `--yes` (see README). Follow it with `tail -f generate.log`.

`generate` saves `kb.xlsx` after every question, so an interrupted run loses nothing: start it again
with "only missing". The first run downloads the models into `models/` and reads every source into
`project/index/`; later runs only read new or changed sources.

To see what kb-builder read from a source, open `project/index/text/<folder>/<file>.txt`. A PDF in
two columns whose text comes out mixed shows up there, and its quotes get ✗ in the Evidence sheet.

## Moving kb.xlsx

kb-builder refuses to save over a `kb.xlsx` that changed since it opened it, so two copies can never
silently overwrite each other. Keep one rule: work on the newest copy (the Runs sheet shows the last
run and machine), and do not have it open in Excel while `generate` or `review` runs.

## Reviewing

On the laptop: copy `project/project.toml` and `project/kb.xlsx` from the server, then double-click the
start file, or run `manage.py review` with the Python in `.venv`. Fill in your name once. Per question:
Accept, Revisions or Reject, a comment, and if needed a final answer. Removing a source marks its
Evidence row "removed" with a reason; the Sources column on the topic sheet then leaves it out.

To check the workbook on a laptop without the sources: `manage.py preflight --workbook-only`.

## Backups

- `project/backups/`: a copy of `kb.xlsx` before every full run.
- Copy `project/` as a whole to a safe place now and then. `project/index/` can be left out: it is
  rebuilt from `materials/`.

## Changing models or prompts

Models: `[model]` in `project/project.toml`; `generate` downloads a new model by itself.
Prompts: `project/prompts/judge.txt` and `answer.txt`. The Runs sheet records a fingerprint of the
prompts and the model for every run, so answers can always be traced to how they were made.

## Updating

Run the start script; it offers a newer version when there is one. A newer Ollama is a change of
`OLLAMA_VERSION` (and, if the release page names it differently, `OLLAMA_ARCHIVE`) in `scripts/start.py`,
made on purpose and noted in `docs/decisions.md`; the start script then replaces the old Ollama by itself.

Each model needs a minimum Ollama version. When `generate` stops with "requires a newer version of
Ollama", raise `OLLAMA_VERSION` to a release that is at least as new as the model.

## Handing over

Hand over the repository (GitHub access), this file, and `/project/` (without `index/`;
`backups/` is optional).
