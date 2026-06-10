# boarding — Steffen airplane boarding-method study

Reproduces Steffen (2008, [arXiv:0802.0733](https://arxiv.org/abs/0802.0733)),
*Optimal boarding method for airline passengers*, in [JuPedSim](https://www.jupedsim.org/).
A standalone study that **uses** [`jupedsim-scenarios`](https://github.com/PedestrianDynamics/jupedsim-scenarios)
(for its direct-steering helpers) but is not part of it.

## What it does

Compares six boarding methods — random, back-to-front, front-to-back, WilMA (outside-in),
Steffen-Perfect, Steffen-Modified — on a single-aisle 30×6 (180-passenger) cabin, and reports the
boarding-time ranking. The model is **logical seating**: agents walk a single-file aisle to their
row, hold for `luggage + seat-interference` time (blocking followers), then sit logically. This
reproduces Steffen's *ranking* (Steffen fastest, back-to-front ≈ random, front-to-back worst); see
`docs/results.md`.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

This pulls `jupedsim` and `jupedsim-scenarios` from PyPI.

## Run the study

```bash
python -m boarding --seeds 20 --rows 30 --out study-output
# or a quick check:
python -m boarding --methods random steffen_perfect --seeds 3 --rows 30 --out /tmp/boarding
```

Outputs `results.csv`, `ranking.csv`, `boarding_times.png`.

## Results

Full 30-row (180-passenger) cabin, 20 paired seeds per method
(`python -m boarding --seeds 20 --rows 30 --out study-output`):

| Rank | Method            | Mean boarding time (s) | Std (s) | vs Steffen-Perfect |
|------|-------------------|------------------------|---------|--------------------|
| 1    | steffen_perfect   | 371.0                  | 3.2     | 1.00×              |
| 2    | steffen_modified  | 378.9                  | 5.2     | 1.02×              |
| 3    | wilma             | 402.2                  | 9.6     | 1.08×              |
| 4    | back_to_front     | 443.0                  | 12.3    | 1.19×              |
| 5    | random            | 455.9                  | 13.0    | 1.23×              |
| 6    | front_to_back     | 615.0                  | 18.5    | 1.66×              |

This reproduces Steffen's ranking: **Steffen-Perfect is fastest**, **Back-to-Front is no better
than Random** (his central counter-intuitive result), and **Front-to-Back is worst**. JuPedSim's
continuous 2-D dynamics compress the absolute ratios versus Steffen's idealized 1-D model, so the
deliverable is the *ranking and relative ordering*, not the absolute "~4×" figure. Artifacts in
`docs/study-output/`; full write-up in `docs/results.md`.

![Boarding time by method](docs/study-output/boarding_times.png)

## Test

```bash
pytest
```

## Layout

- `src/boarding/` — `config`, `geometry` (aisle-only), `methods` (orderings), `choreography`
  (per-agent state machine + penalties), `experiment` (`run_boarding` + `sweep`), `analysis`,
  `seat_placement` (post-hoc seat-fill table), `cli`.
- `docs/` — design spec, implementation plan, results write-up, and a committed study run under
  `docs/study-output/`.

> Note: `docs/design-spec.md` and `docs/implementation-plan.md` reference the original
> `jupedsim-scenarios` paths where this work was first developed; they are kept as the design
> record. The canonical code is here under `src/boarding/`.
