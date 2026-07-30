# Final metadata red-team

Date: 2026-07-30

Frozen inputs:

- `public/tasks_zh.jsonl` SHA-256:
  `2C7A91C1CD621D8DEDC2E74725639DB0BD0297E57174C6A2A1D69AA296BA1CD6`
- `private/gold.jsonl` SHA-256:
  `44AA6922B36B15E9F161A45210069CD90BA49E6E64E7B4F10E629F3E8FD7BC79`

The red team used only non-semantic public metadata. Problem text and evidence
text were excluded. The user-mandated global 25-per-class histogram was not
used to infer a held-out private gold label.

All registered metrics are release gates with a strict failure threshold of
`0.35`:

- maximum fixed-five-fold single-feature accuracy: `0.31`;
- maximum deterministic LOO single/pair/triple accuracy: `0.34`;
- maximum per-feature P95 across 200 hash-fold splits: `0.34`;
- all-feature Laplace categorical decoder: `0.09`;
- fold-fitted all-feature tree: LOO `0.23`, fixed five-fold `0.17`,
  200-fold mean `0.20505`, P95 `0.27`, maximum `0.32`;
- non-global subgroup quota completion: LOO `0.24`, fixed five-fold `0.25`,
  200-fold mean `0.23315`, P95 `0.30`, maximum `0.34`;
- interface-minority decoder: not applicable because every public task exposes
  the same unified evidence semantic-search interface.

The largest release-gated statistic is `0.34 < 0.35`. The audit found no public
field mapping, registered interaction, fold-fitted decoder, or non-global
subgroup quota attack at the failure threshold.
