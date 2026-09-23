# CT Head Rules Engine

> [!WARNING]
> **Not for clinical use.** For teaching only. Not clinically validated or reviewed
> by any regulator. Never use it to decide a patient's care.

Evaluates two head CT decision rules, the **Canadian CT Head Rule** (`cchr`,
Stiell et al., *Lancet* 2001) and the **New Orleans Criteria** (`noc`, Haydel et
al., *N Engl J Med* 2000), and explains each result: which criteria were met,
which inputs are missing, and where in the paper each criterion comes from.

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
- One JSON file works for both rules; each rule reads only the fields it needs.
- `--help` lists that rule's flags, each with the paper's definition.
- Invalid input (such as a misspelt JSON field) is an error, with exit code 2.

## Outcomes

| Outcome | When |
|---|---|
| CT recommended | New Orleans: any of the seven findings is present. |
| CT recommended (high risk) | Canadian: any high-risk criterion is met. The authors called CT mandatory. |
| CT recommended (medium risk) | Canadian: only medium-risk criteria are met. The authors suggest CT or careful observation. |
| CT not required by this rule | The patient is eligible, every input is known, and nothing is met. |
| Rule not applicable | The patient is outside the study population, e.g. GCS 14 for New Orleans, or on an anticoagulant for Canadian. The rule gives no guidance, which is **not** "CT not required". |
| Indeterminate | Nothing is met, but missing inputs prevent a conclusion. |

For example, [`examples/on_warfarin.json`](examples/on_warfarin.json) is "not
applicable" for the Canadian rule even though the patient is 72, a high-risk age.
New Orleans recommends CT (age over 60), with a note that its study could not
evaluate anticoagulated patients.

## How the rules differ

| | Canadian (`cchr`) | New Orleans (`noc`) |
|---|---|---|
| **GCS** | **13–15** | **15 only** |
| Age | 16+; 65+ is high risk | 3+; over 60 is a finding |
| Vomiting | 2 or more episodes | Any |
| Anticoagulants | Exclusion | Not an exclusion, but untested |
| Tiers | High and medium risk | One |

Where the papers define a similar finding differently, such as loss of
consciousness or seizure, each gets its own field; `--help` shows each
definition. The only link between the two: a Canadian skull fracture sign that
is present also counts as New Orleans trauma above the clavicles.

## Interpretation choices

For the Canadian rule, where the paper is inconsistent, Panel 1 (the rule as
published) wins.

| Question | Choice |
|---|---|
| Amnesia before impact | More than 30 min (Panel 1), not 30 min or more (Tables 3 and 6) |
| Dangerous mechanism | Panel 1's three mechanisms, not Table 4's wider list |
| Depressed skull fracture | Suspected is high risk; obvious is an exclusion |
| Less than 2 h since injury | GCS at 2 h is unknown, so indeterminate, with a note to re-evaluate |
| Newer anticoagulants | Left to the user; the paper names only Coumadin |
| Criterion met, eligibility unknown | CT recommended, with the missing input flagged (both rules) |
| New Orleans: GCS 14 from a memory deficit alone | Not re-scored automatically; a note says the paper scored this as 15 |
| New Orleans: declined CT, or injuries ruling out CT | Study exclusions, not implemented |

## Development

```bash
pytest
```

```bash
ruff check . && ruff format --check .
```

CI runs both on every push, on Python 3.11–3.13. Project conventions are in
[`CLAUDE.md`](CLAUDE.md).

## Sources

- Stiell IG, Wells GA, Vandemheen K, et al. The Canadian CT Head Rule for
  patients with minor head injury. *Lancet* 2001;357:1391–96. Eligibility:
  Methods (pp1391–92). Criteria: Panel 1 (p1394).
- Haydel MJ, Preston CA, Mills TJ, et al. Indications for computed tomography in
  patients with minor head injury. *N Engl J Med* 2000;343:100–05. Eligibility
  and the seven findings: Methods (pp100–01).

The PDFs are copyrighted and not included here;
[`sources/README.md`](sources/README.md) lists them.

## License

[MIT](LICENSE), provided "as is" without warranty. It covers this code only, not
the cited papers.
