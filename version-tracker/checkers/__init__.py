"""checkers/ — version-source runtime package.

Modules here are invoked by the runner. We import the sibling http_cache
module here so that any downstream `from checkers.http_cache import ...`
sees the same Python class object as `from checkers.runner import http_cache`.
Without this, the same .py file is loaded twice (once as `http_cache`, once
as `checkers.http_cache`), creating two distinct class objects — and
`except http_cache.RedirectBlockedError` would never match an exception
raised from a class that came from the second copy.
"""

from checkers import http_cache  # noqa: F401  — re-export the sibling module
from checkers import identity  # noqa: F401  — sibling module, also imported here