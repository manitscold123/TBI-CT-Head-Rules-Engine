# CT Head Rules Engine

Educational implementation of clinical decision rules for head CT imaging.
Currently implements the **Canadian CT Head Rule** (Stiell et al., 2001).

> [!WARNING]
> **Not for clinical use.** This software is for teaching and software-engineering
> practice only. It has not been clinically validated, reviewed by a regulator, or
> tested in any care setting. Do not use it to decide whether a patient receives
> imaging or any other care. The rule's own authors described it as a derivation
> study that still needed prospective validation. Clinical decisions belong to a
> qualified clinician using current local guidelines.

## Installation

Requires Python 3.11 or later.

```bash
git clone <repository-url>
cd ct-head-rules
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `ct-head-rules` command. `python -m ct_head_rules` works too.

## Usage

Give patient findings as flags, as a JSON file, or both. Flags override the file.

**Any finding you don't supply is treated as unknown, never as absent.** A result
of "CT not required" is only possible when every input the rule needs is known.

### Flags

Yes/no findings take `present`, `absent` or `unknown`. Numeric findings take a
number. Run `ct-head-rules cchr --help` for the full list.

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

### JSON file

Print a template with every finding set to unknown, fill it in, then pass it with
`--json`:

```bash
ct-head-rules cchr --template > patient.json
```

```bash
ct-head-rules cchr --json patient.json
```

In the file, yes/no findings are `"present"`, `"absent"` or `"unknown"` (or
`null`), and numeric findings are numbers or `null`. A field left out of the file
is unknown. A misspelt field name is an error, so a typo can't quietly become a
missing input.

Two complete examples are in [`examples/`](examples/):

```bash
ct-head-rules cchr --json examples/on_warfarin.json
```

```text
Canadian CT Head Rule (Stiell et al., Lancet 2001)
Educational use only. NOT for clinical use.

Outcome: Rule not applicable to this patient

Rule does not apply because:
  - Oral anticoagulant use [Stiell 2001, Lancet 357:1391-96, Methods: Study setting and population (p1392)]

Notes:
  - The Canadian CT Head Rule was not derived for this patient and gives no guidance on CT. This is not a 'CT not required' result.
```

That patient is 72, which is a high-risk criterion, but the rule's study excluded
patients on oral anticoagulants, so the rule gives no answer either way.

### Machine-readable output

Add `--format json` to get the outcome, the triggered criteria, the missing
inputs, and every criterion's status and source:

```bash
ct-head-rules cchr --json examples/minor_head_injury.json --pedestrian-struck-by-motor-vehicle present --format json
```

```json
{
  "rule": "cchr",
  "disclaimer": "Educational use only. NOT for clinical use.",
  "outcome": "ct_recommended",
  "risk_level": "medium",
  "triggered": ["cchr.medium.dangerous_mechanism"],
  "exclusion_reasons": [],
  "missing_inputs": [],
  "notes": ["Medium risk only: the authors suggest CT or careful observation, depending on local resources (Stiell 2001, Discussion p1396)."],
  "criteria": [ ... ]
}
```

### Outcomes

| Outcome | Meaning |
|---|---|
| CT recommended (high risk) | At least one high-risk criterion is met. The authors considered CT mandatory. |
| CT recommended (medium risk) | Only medium-risk criteria are met. The authors suggest CT or careful observation, depending on local resources. |
| CT not required by this rule | The patient is eligible, every input is known, and no criterion is met. |
| Rule not applicable to this patient | The patient is outside the population the rule was derived in (for example, on an oral anticoagulant, under 16, or GCS below 13). The rule gives no guidance, which is **not** the same as "CT not required". |
| Indeterminate | Nothing is met, but missing inputs mean the rule can't conclude. The output lists what is needed. |

Exit status is 0 when a result is printed and 2 for invalid input.

## Interpretation choices

Where the paper is ambiguous or inconsistent, this implementation follows Panel 1
(the rule as published). These choices are also noted in the code:

- **Amnesia before impact:** more than 30 min (Panel 1), not 30 min or more (Tables 3 and 6).
- **Dangerous mechanism:** the three mechanisms in Panel 1, not the wider Table 4 footnote.
- **Suspected vs obvious depressed fracture:** suspected is high risk; obvious is an exclusion.
- **GCS at 2 h:** before 2 h have passed it is unknown, so the result is indeterminate with a note to re-evaluate.
- **Oral anticoagulants:** the paper names Coumadin as its example. Whether newer anticoagulants count is left to the caller.
- **Unknown eligibility with a met criterion:** CT is still recommended, with the missing input flagged. The missing information could only make the rule not apply; it could never make CT unnecessary.

## Development

```bash
pytest
```

```bash
ruff check . && ruff format --check .
```

Conventions are in [`CLAUDE.md`](CLAUDE.md). In short: every criterion cites the
paper and page it comes from, criteria are taken from the papers in `sources/`
(local copies; see [`sources/README.md`](sources/README.md)) and never from memory, tests are written first, and unknown inputs are never
treated as negative. A test checks each criterion's cited pages.

GitHub Actions runs ruff and pytest on Python 3.11, 3.12 and 3.13 on every push.

## Citations

Canadian CT Head Rule:

> Stiell IG, Wells GA, Vandemheen K, Clement C, Lesiuk H, Laupacis A, McKnight RD,
> Verbeek R, Brison R, Cass D, Eisenhauer MA, Greenberg GH, Worthington J, for the
> CCC Study Group. The Canadian CT Head Rule for patients with minor head injury.
> *Lancet* 2001;357:1391–96.

The eligibility and exclusion criteria come from the Methods section (pp1391–92).
The high- and medium-risk criteria come from Panel 1 (p1394).

The source PDFs are copyrighted and not included in this repository.
[`sources/README.md`](sources/README.md) lists each paper and the filename to save
it under, including two papers for rules not yet implemented: Haydel et al.
(*N Engl J Med* 2000) and Kuppermann et al. (*Lancet* 2009).

## License

[MIT](LICENSE). The license provides the software "as is", without warranty of
any kind. That applies alongside, not instead of, the warning at the top of this
page: this software is **not for clinical use**.

The license covers this repository's code only. It grants no rights to the cited
papers.
