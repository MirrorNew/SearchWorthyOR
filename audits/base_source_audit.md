# SearchWorthyOR-100 base source audit

## Result

Static base selection passed: exactly **100** distinct candidate skeletons were
written as **57 OptMinerBench + 33 NLP4LP + 10 MAMO-ComplexLP**. The planned
60-row OptMinerBench quota was reduced because only 57 rows passed the linear
LP/MILP/IP screen; as pre-registered, the three-row deficit was filled from
NLP4LP rather than retaining NLP/SOCP rows.

This is a source-screening artifact only. It does **not** solve any instance,
certify any objective, create gold answers, or make a final release decision.
Legacy `answer` and `code` fields are not copied into the candidate payload.
Their provenance status is recorded as pending review / not gold.

## Count and uniqueness checks

| Check | Observed | Required | Result |
|---|---:|---:|---|
| Total rows | 100 | 100 | PASS |
| OptMinerBench rows | 57 | 57 | PASS |
| NLP4LP rows | 33 | 33 | PASS |
| MAMO-ComplexLP rows | 10 | 10 | PASS |
| Unique `candidate_id` | 100 | 100 | PASS |
| Unique `(source_dataset, source_id)` | 100 | 100 | PASS |
| Unique normalized problem SHA256 | 100 | 100 | PASS |
| Rows with the exact required key set | 100 | 100 | PASS |
| Rows marked `selected_for_manual_review` | 100 | 100 | PASS |

`source_hash` is SHA256 over the UTF-8 bytes of the problem after Unicode NFKC
normalization, whitespace collapse, and outer-whitespace trimming. It is a
source-text identity check, not a semantic-equivalence or answer-correctness
certificate.

## Selection policy

### OptMinerBench

- Input rows: 128; statically eligible after the union of exclusions and the
  LP/MILP/IP type screen: 57; all 57 were retained.
- Exact duplicate handling: keep `OMB007`; remove `OMB033`, which has the same
  normalized problem hash.
- Legacy-code syntax failures (27; overlaps other
  categories): `OMB014`, `OMB031`, `OMB037`, `OMB046`, `OMB049`, `OMB050`, `OMB053`, `OMB056`, `OMB057`, `OMB058`, `OMB062`, `OMB063`, `OMB065`, `OMB067`, `OMB068`, `OMB077`, `OMB079`, `OMB080`, `OMB081`, `OMB086`, `OMB097`, `OMB098`, `OMB100`, `OMB118`, `OMB121`, `OMB124`, `OMB127`.
- Explicit multi-objective markers (17; overlaps
  other categories): `OMB002`, `OMB013`, `OMB015`, `OMB024`, `OMB040`, `OMB047`, `OMB054`, `OMB062`, `OMB067`, `OMB084`, `OMB088`, `OMB098`, `OMB105`, `OMB111`, `OMB120`, `OMB121`, `OMB124`.
- Legacy problem/code hidden-instance or synthetic-data markers
  (15; overlaps other categories):
  `OMB019`, `OMB048`, `OMB055`, `OMB066`, `OMB074`, `OMB101`, `OMB102`, `OMB103`, `OMB105`, `OMB106`, `OMB108`, `OMB111`, `OMB114`, `OMB116`, `OMB120`.
- Locally documented problem/reference, hidden-instance, or solver-history risks
  (23; overlaps other categories):
  `OMB010`, `OMB053`, `OMB063`, `OMB085`, `OMB100`, `OMB101`, `OMB102`, `OMB103`, `OMB104`, `OMB105`, `OMB108`, `OMB109`, `OMB110`, `OMB111`, `OMB113`, `OMB114`, `OMB115`, `OMB117`, `OMB120`, `OMB122`, `OMB124`, `OMB126`, `OMB128`.
- Nonlinear `NLP`/`SOCP` type IDs rejected before certification:
  `OMB005`, `OMB008`, `OMB014`, `OMB016`, `OMB021`, `OMB040`, `OMB041`,
  `OMB052`, `OMB065`, `OMB074`, `OMB089`, `OMB093`, `OMB121`.
- Selected source IDs: `OMB001`, `OMB003`, `OMB004`, `OMB006`, `OMB007`, `OMB009`, `OMB011`, `OMB012`, `OMB017`, `OMB018`, `OMB020`, `OMB022`, `OMB023`, `OMB025`, `OMB026`, `OMB027`, `OMB028`, `OMB029`, `OMB030`, `OMB032`, `OMB034`, `OMB035`, `OMB036`, `OMB038`, `OMB039`, `OMB042`, `OMB043`, `OMB044`, `OMB045`, `OMB051`, `OMB059`, `OMB060`, `OMB061`, `OMB064`, `OMB069`, `OMB070`, `OMB071`, `OMB072`, `OMB073`, `OMB075`, `OMB076`, `OMB078`, `OMB082`, `OMB083`, `OMB087`, `OMB090`, `OMB091`, `OMB092`, `OMB094`, `OMB095`, `OMB096`, `OMB099`, `OMB107`, `OMB112`, `OMB119`, `OMB123`, `OMB125`.

The overlap note matters: the category counts above must not be added together.
All selected OMB rows pass every listed static screen. Parsing old code only
checks Python syntax; the old code remains `pending_manual_review_not_gold`.

### NLP4LP

- Input rows: 242; eligible after complete-text,
  terminal-punctuation, exact-dedup, single-objective-direction, and
  hidden/external-data-marker screens: 233.
- Selection: 33 deterministic source-order quantiles across the eligible pool,
  avoiding a first-33/order-prefix sample.
- Rejection counts with overlap:
  `{"mixed_objective_directions": 4, "objective_direction_missing": 5}`.
- Selected source IDs: `nlp4lp_000001`, `nlp4lp_000008`, `nlp4lp_000015`, `nlp4lp_000023`, `nlp4lp_000030`, `nlp4lp_000037`, `nlp4lp_000046`, `nlp4lp_000055`, `nlp4lp_000062`, `nlp4lp_000070`, `nlp4lp_000077`, `nlp4lp_000085`, `nlp4lp_000092`, `nlp4lp_000099`, `nlp4lp_000108`, `nlp4lp_000115`, `nlp4lp_000122`, `nlp4lp_000129`, `nlp4lp_000136`, `nlp4lp_000144`, `nlp4lp_000151`, `nlp4lp_000158`, `nlp4lp_000166`, `nlp4lp_000173`, `nlp4lp_000181`, `nlp4lp_000189`, `nlp4lp_000197`, `nlp4lp_000205`, `nlp4lp_000213`, `nlp4lp_000220`, `nlp4lp_000228`, `nlp4lp_000235`, `nlp4lp_000242`.
- Source `scenario` and `type` fields are blank. The output preserves this fact as
  `scenario="Unspecified"` and uses the dataset-level label `type="LP-family"`;
  `static_audit.metadata_origin` records those origins.

### MAMO-ComplexLP

- Input rows: 211; eligible under the same
  supplemental-pool static screens: 189.
- Selection: 10 curated, screen-passing, exact-unique rows with 10 distinct
  formulation types: `LP`, `transportation`, `network_flow`, `TSP`, `facility_location`, `scheduling`, `shortest_path`, `portfolio`, `set_cover`, `inventory`.
- Rejection counts with overlap:
  `{"missing_terminal_punctuation": 1, "mixed_objective_directions": 15, "objective_direction_missing": 6}`.
- Selected source IDs: `mamo_complexlp_000001`, `mamo_complexlp_000041`, `mamo_complexlp_000049`, `mamo_complexlp_000060`, `mamo_complexlp_000140`, `mamo_complexlp_000179`, `mamo_complexlp_000186`, `mamo_complexlp_000198`, `mamo_complexlp_000200`, `mamo_complexlp_000207`.

## SHA256 verification

| Artifact | Relative path | SHA256 |
|---|---|---|
| Input: OptMinerBench | `benchmark/optminer_bench.jsonl` | `7e57c0a01745cbdaf32ce51d86345045ed584242030fc07865ad5d76c2c6c81c` |
| Input: NLP4LP | `benchmark/nlp4lp.jsonl` | `950a43472219c2f37d74e377c4b0c1e0fc39fadb6deef487eab6eeee8fa7e036` |
| Input: MAMO-ComplexLP | `benchmark/mamo_complexlp.jsonl` | `821271ddc850f6e88273bc19f4443c60905d0465d216d1e670881a092778971d` |
| Builder | `datasets/SearchWorthyOR-100/scripts/build_base_candidates.py` | `1550d6f6412e024ceed7938c5fc9f7b14d1be050223bc42418bc75f5baabb367` |
| Output | `datasets/SearchWorthyOR-100/staging/base_candidates.jsonl` | `e58f6929ecf00db298de2ecb10407ad1abb2b7249bbb2ce3684db6a4b09cd2d4` |

The audit Markdown does not list its own SHA256 because embedding a file's hash
inside that same file is self-referential. The builder and generated JSONL are
both covered. The builder only regenerates the JSONL; this audit Markdown is
maintained separately with patch-based edits.

## Boundary and next gate

Every row is intentionally left at `selected_for_manual_review`. A later stage
must independently review formulation fidelity, objective direction, solver
compatibility, answer provenance, and any final release criteria. Static passage
here must not be interpreted as solver certification or release readiness.
