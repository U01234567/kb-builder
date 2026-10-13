# Decisions

Why kb-builder works the way it does. Project-specific choices live in `/project/README.md`.

## Shape

- **Two machines, one repository.** Generating needs GPUs (a Linux server); reviewing needs a browser.
  The same repository runs on both; only `kb.xlsx` travels.
- **Excel is the store.** Questions, answers, evidence and reviews all live in `kb.xlsx`, so it can be
  sent to supervisors as it is. There is no database.
- **Django, stripped down.** Templates, forms, CSRF and management commands; no database, admin or
  accounts. The review app only listens on `127.0.0.1`.
- **Topics read their own folders.** The Topics sheet maps each topic to folders in `materials/`
  (`*` for all). Nobody assigns sources per question: the model decides which passages carry the answer.
- **Stable numbers where things refer to each other.** Questions (Q001) and sources (S001) get numbers
  kb-builder hands out. Sources are also recognised by a fingerprint of their content, so moving or
  renaming a file changes nothing.
- **One truth per fact.** Sources live in the Evidence sheet only; the Sources column on a topic sheet,
  the titles in Evidence and the Overview are derived and rewritten on every save (grey headers).
- **A preflight before every run**, also on its own: x stops a run, ! warns.

## Answering

- **Search by meaning and by words** (so numbers like 2,50 are found), within the topic's folders,
  merged by reciprocal rank fusion.
- **The model is the judge.** It sees many candidate passages and says per passage whether it carries
  the answer. Only those reach the answer prompt. No passage: "not found".
- **Quotes are checked.** Every quote must literally appear in its source (✓/✗), re-checked on every run,
  so a changed or deleted source shows which answers may be out of date.
- **A full run clears the reviews of what it regenerates;** the backup keeps the old ones.

## Dependencies

Each package below is pinned in `requirements.txt` to patch updates only (`~=X.Y.0`), together with the
packages it pulls in. A minor or major upgrade is a deliberate change with a line here.

- **Django 5.2 (LTS):** the review app and the commands. Long-term support, so patch updates for years.
- **openpyxl:** reading and writing `kb.xlsx` with tables, colours and drop-downs. CSV cannot hold those.
- **pypdf:** text from PDFs, no further dependencies. Known limit: PDFs whose two columns are stored
  line by line across both columns come out mixed; see `project/index/text/` and the ✗ marks.
- **Ollama** (not a Python package): runs the language and embedding models on the GPUs, with output
  forced into a JSON schema. Pinned in `scripts/start.py`; talked to with the standard library.
- Everything else (HTML reading, search index, TOML, HTTP) is Python's standard library.
