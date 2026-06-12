# Why don't airlines board planes the optimal way? I rebuilt the classic studies in JuPedSim to find out

*A LinkedIn article — draft. Suggested cover image: `docs/study-output/comparison.gif`.*

---

There's a famous result in physics-meets-operations-research: in 2008, astrophysicist Jason Steffen worked out the **mathematically optimal way to board an airplane**. It boards passengers in a precise interleaved order — window seats first, every other row — so that many people stow their luggage at the same time and nobody ever has to climb over a seated neighbour. In ideal conditions it's dramatically faster than how airlines actually do it.

And here's the twist that always gets people: **boarding back-to-front — what many airlines use — is no better than boarding everyone at random.** Front-to-back is *worse* than random.

So why does no airline use Steffen's method? I rebuilt these studies in [JuPedSim](https://www.jupedsim.org/), our open-source pedestrian-dynamics simulator, to see the answer move.

## Step 1 — reproduce the classic ranking

I modelled a single-aisle 180-seat cabin and ran six boarding strategies. Each passenger walks the aisle to their row, holds there while they stow luggage and let neighbours shuffle past (the two things that actually cause boarding delays), then sits. Same geometry, same luggage draws, 20 repetitions per method.

**[Insert: `docs/study-output/comparison.gif`]** — six methods boarding side by side; watch the Steffen variants pull ahead while front-to-back jams.

The ranking comes out exactly as the literature says: **Steffen fastest, back-to-front barely better than random, front-to-back worst.**

**[Insert: `docs/study-output/boarding_times.png`]**

So far, so textbook. The interesting part is the next question.

## Step 2 — why the optimum stays on paper

Steffen's method assumes 180 strangers will form one perfect single-file queue and board in a strict choreographed order. Real passengers don't. Families board together. People show up late. Not everyone follows the plan.

A very recent paper — **Dong, Yanagisawa & Nishinari (2025), *Physica A***, on boarding the future blended-wing-body aircraft — quantified one of these effects: a **compliance rate**, the share of passengers who actually board in their assigned slot. I reproduced their compliance sweep on my single-aisle cabin.

**[Insert: `docs/study-output/comparison_compliance.gif`]** — the same method at 100% vs 50% compliance. The **red dots are passengers boarding out of their assigned slot**; the 50% panel finishes visibly later.

The result is striking and matches their paper: as compliance drops, **the clever methods lose their edge and slide toward random boarding**, while random itself barely changes. At zero compliance every method gives the same time — because nobody is following any order, so there *is* no order.

**[Insert: `docs/study-output/compliance_erosion.png`]**

Two completely different models — their discrete cellular automaton on a wide multi-aisle aircraft, my continuous pedestrian simulation on a narrow-body — agree on the trend. That cross-check is the fun part of reproducing someone else's work.

## Step 3 — the optimum is the fragile one

I pushed the same idea two more ways. I gave passengers **realistic profiles** (fast young travellers, heavy luggage, elderly with reduced mobility, families with kids), and I let **travel groups board together** instead of in perfect order.

Same story every time: **Steffen's "perfect" method is the most fragile.** It's the most sensitive to a mixed passenger crowd, it's the *only* method that gets slower as more people travel in groups, and it loses its whole advantage when people don't comply. Meanwhile a coarser, **practical** Steffen-style variant — one real passengers could plausibly follow — stays robust and overtakes the optimum.

**[Insert: `docs/study-output/group_erosion.png`]** — boarding time as travel groups grow; the optimum rises while the practical variant holds flat.

That's the answer to the headline question, in one line: **the value of a clever boarding order is almost entirely contingent on passengers following it** — and the optimum is the first casualty of real human behaviour.

## What this is (and isn't)

I want to be straight about this: it's not new science. Steffen showed the ranking in 2008 and confirmed it experimentally in 2012; Dong et al. did the robustness analysis in 2025. **What I built is a reproduction and a showcase** — a demonstration that JuPedSim can model this whole problem from a few lines of Python, that the studies replicate across very different simulation engines, and that the entire pipeline is open and re-runnable.

Everything here — model, experiments, every figure and video — is on GitHub, and each plot regenerates with one command:

👉 **Code & data:** https://github.com/chraibi/boarding
👉 **JuPedSim:** https://www.jupedsim.org/

Credit where it's due: **Jason Steffen** for the original optimal-boarding work, and **Yuming Dong, Daichi Yanagisawa & Katsuhiro Nishinari** for the recent robustness study I reproduced.

If you've ever stood in a jet bridge wondering why this takes so long — now you can watch the simulation and see exactly where it jams.

*#PedestrianDynamics #JuPedSim #Simulation #OperationsResearch #ReproducibleResearch #AirplaneBoarding*

---

### Posting notes (not part of the article)

- LinkedIn renders **native video** better than GIFs — consider uploading the `.mp4` versions (`comparison.mp4`, `comparison_compliance.mp4`) as a short video, or convert the GIFs.
- Suggested image order: cover = `comparison.gif`; then `comparison_compliance.gif` (the red-dot one is the most arresting); then the two erosion plots.
- A model schematic is available at `blog/figures/model.png` if you want to show how the cabin/holds work.
- Keep it to ~3–4 images/clips; LinkedIn truncates long articles — the hook + the compliance clip carry it.
