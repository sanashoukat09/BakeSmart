# Independent expert review

`expert_review_assignments_v1.csv` contains two independent assignments for
each of the 120 stratified review scenarios. The recommendation labels remain
synthetic until humans complete both reviewer slots.

## Reviewer rules

- Reviewer slots 1 and 2 must be completed independently by different people.
- Use a stable pseudonymous `expert_id`; do not enter personal contact details.
- Allowed `expert_role` values are `baker`, `event_decorator`, and
  `baker_and_event_decorator`.
- Set `review_decision` to `approve`, `correct`, or `reject`.
- For `approve`, explicitly copy all four current labels into the expert label
  columns.
- For `correct`, enter all four expert labels, change at least one label, and
  explain the correction in `comments`.
- For `reject`, explain why the scenario cannot be labelled reliably.
- Set `expert_confidence` from 1 to 5.
- Set `reviewed_at_utc` using ISO 8601, for example `2026-08-18T10:30:00Z`.
- Do not change scenario inputs, current labels, assignment IDs, or reviewer
  slots.

Run the audit after reviewers save the file:

```powershell
python -m training.review_dataset
```

To require all 240 assignments to be completed:

```powershell
python -m training.review_dataset --require-complete
```

The audit validates decisions and labels, requires independent expert IDs, and
calculates observed agreement and Cohen's kappa when paired reviews exist.
