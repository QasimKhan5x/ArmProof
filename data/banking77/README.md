# BANKING77 Reference Workload

ArmProof uses BANKING77 as a realistic, public support-routing workload. The
official dataset contains 13,083 online-banking requests across 77 fine-grained
intents. This repository stores the official test split and category list from
PolyAI commit `57ec275d8078af65b7731c2a98be812d844a6d6b`.

The upstream dataset is licensed CC-BY-4.0. See
`source/LICENSE-CC-BY-4.0`. Cite:

> Inigo Casanueva, Tadas Temcinas, Daniela Gerz, Matthew Henderson, and Ivan
> Vulic. Efficient Intent Detection with Dual Sentence Encoders. NLP4ConvAI,
> 2020.

Rebuild and verify deterministic derived files:

```bash
python3.12 scripts/build_banking77_workload.py
```

`quality.jsonl` contains 770 examples: the first ten official test examples
for every intent. The three 512-row traffic sets represent concise routing,
detailed routing with rationale, and a 50/50 mixture. These are benchmark
fixtures, not financial advice or a production banking policy.
