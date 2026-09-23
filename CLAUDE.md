# CT Head Rules Engine
Educational implementation of clinical decision rules for head CT imaging.
Not for clinical use.

## Conventions
- Python 3.11+, pytest for tests, ruff for linting
- Every criterion in code must cite its source (paper + table/section) in a comment
- Source criteria live in sources/; never implement a criterion from memory
- Write tests before implementation
- Unknown/missing inputs must never be silently treated as "negative"
