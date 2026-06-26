"""Enable ``python -m dramaturgy`` as an alias for the ``dra`` CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
