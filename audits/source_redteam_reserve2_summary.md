# Reserve2 source red-team summary

- Rows: 40
- Pass: 40
- Reject: 0
- Independent dual-solver recheck: PASS
- Frozen manifest and inputs: PASS
- Manual text-to-IR semantic review: PASS
- Original 140-row red-team file unchanged: YES
- Output SHA-256: `197fdcb7e9a78b4d44d9f3daf965a54b3ccb2329af67a28bf4bf13a04214f60c`

The generator verdict was not used as semantic authority. Every source was reviewed against its frozen NLP4LP text, and each current IR was rebuilt independently in Gurobi and COPT with recomputed objective, residual, bound, and integrality checks.
