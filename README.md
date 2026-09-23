# CT Head Rules Engine

> [!WARNING]
> **Not for clinical use.** For teaching only. Not clinically validated or reviewed
> by any regulator. Never use it to decide a patient's care.

Evaluates the **Canadian CT Head Rule** (Stiell et al., *Lancet* 2001) and explains
each result: which criteria were met, which inputs are missing, and where in the
paper each criterion comes from.

## Install

Requires Python 3.11+.

```bash
git clone https://github.com/manitscold123/TBI-CT-Head-Rules-Engine.git
cd TBI-CT-Head-Rules-Engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Use

```bash
ct-head-rules cchr --json examples/minor_head_injury.json --vomiting-episodes 2 --battle-sign unknown
```

```text
Canadian CT Head Rule (Stiell et al., Lancet 2001)
Educational use only. NOT for clinical use.

Outcome: CT recommended (high risk)

Triggered criteria:
  - Vomiting 2 or more episodes [Stiell 2001, Lancet 357:1391-96, Panel 1 (p1394)]

Missing inputs:
  - battle_sign (--battle-sign)
```

- **Anything you don't supply is unknown, never absent.**
- Give findings as flags, a JSON file (`--json FILE`), or both. Flags override the file.
- Yes/no findings take `present`, `absent` or `unknown`. Others take a number.
- `--template` prints a JSON file with every finding unknown, ready to fill in.
- `--format json` gives machine-readable output, including every criterion's status and source.
- `--help` lists every flag.
- Invalid input (such as a misspelt JSON field) is an error, with exit code 2.

## Outcomes

| Outcome | When |
|---|---|
| CT recommended (high risk) | Any high-risk criterion is met. The authors called CT mandatory. |
| CT recommended (medium risk) | Only medium-risk criteria are met. The authors suggest CT or careful observation. |
| CT not required by this rule | The patient is eligible, every input is known, and nothing is met. |
| Rule not applicable | The patient is outside the study population, e.g. on an anticoagulant, under 16, or GCS below 13. The rule gives no guidance, which is **not** "CT not required". |
| Indeterminate | Nothing is met, but missing inputs prevent a conclusion. |

For example, [`examples/on_warfarin.json`](examples/on_warfarin.json) is "not
applicable" even though the patient is 72, a high-risk age.

## Interpretation choices

Where the paper is inconsistent, Panel 1 (the rule as published) wins.

| Question | Choice |
|---|---|
| Amnesia before impact | More than 30 min (Panel 1), not 30 min or more (Tables 3 and 6) |
| Dangerous mechanism | Panel 1's three mechanisms, not Table 4's wider list |
| Depressed skull fracture | Suspected is high risk; obvious is an exclusion |
| Less than 2 h since injury | GCS at 2 h is unknown, so indeterminate, with a note to re-evaluate |
| Newer anticoagulants | Left to the user; the paper names only Coumadin |
| Criterion met, eligibility unknown | CT recommended, with the missing input flagged |

## Development

```bash
pytest
```

```bash
ruff check . && ruff format --check .
```

CI runs both on every push, on Python 3.11–3.13. Project conventions are in
[`CLAUDE.md`](CLAUDE.md).

## Source

Stiell IG, Wells GA, Vandemheen K, et al. The Canadian CT Head Rule for patients
with minor head injury. *Lancet* 2001;357:1391–96.

Eligibility comes from Methods (pp1391–92) and the criteria from Panel 1 (p1394).
The PDFs are copyrighted and not included here;
[`sources/README.md`](sources/README.md) lists them.

## License

[MIT](LICENSE), provided "as is" without warranty. It covers this code only, not
the cited papers.
