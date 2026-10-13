# Project folder

`/project/` holds one project: its settings, prompts, sources and knowledge base. It is never committed
(it is in `.gitignore`); `start.py` creates it from this example the first time.

| Path | What it is | Who edits it |
|---|---|---|
| `project.toml` | Models, GPUs, column headers, number of question variants | you |
| `prompts/judge.txt` | How the model judges which passages carry the answer (`$question`, `$passages`) | you |
| `prompts/answer.txt` | How the model writes the answer (`$question`, `$passages`, `$variants`) | you |
| `materials/<folder>/` | Sources as `.pdf`, `.html` or `.htm`, one folder per subject | you |
| `kb.xlsx` | The questions (one sheet per topic, with a `Question` column) and everything kb-builder adds | you and kb-builder |
| `index/` | The search index and a readable text version of every source (`index/text/`) | kb-builder |
| `backups/` | A copy of `kb.xlsx` before every full run | kb-builder |

In `kb.xlsx`, the **Topics** sheet says which folders each topic reads: folder names separated by commas,
or `*` for all folders. New topics get a guessed folder; check it before a run.
