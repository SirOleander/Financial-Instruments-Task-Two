"""DEPRECATED shim — the real module is `fi.sec`.

Kept so `G_operative` (which uses make_session / request_json / fetch_submissions /
fetch_filing_document / list_filing_inline_documents) keeps importing `C_client`
unchanged until it moves. Deleted once its last importer has moved.
"""
from fi.sec import *  # noqa: F401,F403
