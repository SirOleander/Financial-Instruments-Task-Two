---
name: aconfig-crlf-gotcha
description: src/A_config.py is committed with CRLF under autocrlf=true — Edit-tool edits show spurious whole-block line-ending diffs
metadata:
  type: reference
---

`src/A_config.py` is stored in git with **CRLF** line endings while the repo has
`core.autocrlf=true`. The Edit/Write tools write **LF**, so editing A_config makes
`git diff` show a large spurious "change" (e.g. the ~79-line SECTOR_BY_TICKER block)
that is **content-identical** — pure CRLF↔LF noise, not a real change.

**How to tell it's noise:** `git diff -w --numstat -- src/A_config.py` (ignore whitespace)
shows the true content delta; if that's just your intended lines, the rest is line-ending.

**How to keep a clean, content-only commit when editing A_config:** rebuild the file as
`your-change + exact committed bytes` and stage with autocrlf off, e.g.
`git cat-file blob HEAD:src/A_config.py` → prepend/patch with CRLF-matched text →
`git -c core.autocrlf=false add src/A_config.py`. Other src/*.py are LF and edit cleanly.

Discovered during the Tier-1 professionalization commit (a94ad16) when adding the module
docstring to A_config. See [[operative-scores]] / [[scores-table]] for the pipeline context.
