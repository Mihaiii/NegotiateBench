import math
import random
from typing import List, Optional, Tuple


class Agent:
    """
    Incoming offer o: opponent proposes OUR share.
    Return None to accept (only if o is not None).
    Return list to counter: OUR desired share.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))
        self.sum_counts = max(1, sum(self.counts))

        self.turn = 0  # our turn index (0-based)
        self.best_seen = 0

        self.pos_idx = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        self.zero_idx = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] == 0]

        self.their_last: Optional[List[int]] = None
        self.my_last_offer: Optional[List[int]] = None
        self.last_ask_value: Optional[int] = None

        # Enumeration over positive-value types (zero-value types always 0 for us).
        max_enum = 120000
        space = 1
        for i in self.pos_idx:
            space *= (self.counts[i] + 1)
            if space > max_enum:
                break
        self._enum_ok = (space <= max_enum and self.total > 0)

        self._offers: List[Tuple[int, List[int]]] = []  # (my_value, offer)
        if self._enum_ok:
            cur = [0] * len(self.pos_idx)

            def rec(k: int):
                if k == len(self.pos_idx):
                    off = [0] * self.n
                    for j, idx in enumerate(self.pos_idx):
                        off[idx] = cur[j]
                    mv = self._my_value(off)
                    self._offers.append((mv, off))
                    return
                idx = self.pos_idx[k]
                for x in range(self.counts[idx] + 1):
                    cur[k] = x
                    rec(k + 1)

            rec(0)
            self._offers.sort(key=lambda t: t[0], reverse=True)
        else:
            self._offers = self._build_greedy_ladder()

        # Particle filter over opponent unit values mu (floats), normalized so sum(counts*mu)=total.
        self.rng = random.Random(1)
        self.P = 260 if self.n <= 7 else 220
        self.particles = self._init_particles(self.P)
        self.logw = [0.0] * len(self.particles)  # log weights

        self._last_pick_pacc = 0.0  # filled by _pick_counter()

    # ------------------------- basic utils -------------------------

    def _valid_offer(self, o) -> bool:
        if not isinstance(o, (list, tuple)) or len(o) != self.n:
            return False
        for i, x in enumerate(o):
            if not isinstance(x, int):
                return False
            if x < 0 or x > self.counts[i]:
                return False
        return True

    def _my_value(self, share: List[int]) -> int:
        return sum(self.values[i] * share[i] for i in range(self.n))

    def _is_last_our_turn(self) -> bool:
        return self.turn >= self.max_rounds - 1

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        overall = 2 * self.turn + self.me
        denom = 2 * self.max_rounds - 1
        return max(0.0, min(1.0, overall / denom))

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x <= -35.0:
            return 0.0
        if x >= 35.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-x))

    def _base_ask(self) -> List[int]:
        # Keep everything with positive value; give away our zero-value types.
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    # ------------------------- thresholds -------------------------

    def _their_threshold(self, p: float) -> float:
        # Estimated opponent minimum value (in THEIR units); decreases with time.
        frac = 0.78 - 0.60 * (p ** 1.10)  # ~0.78 -> ~0.18
        frac = max(0.20, min(0.80, frac))
        return frac * self.total

    def _my_floor(self, p: float) -> float:
        if self.total <= 0:
            return 0.0
        last = self._is_last_our_turn()

        # If we're second and it's our last turn, counter cannot be accepted; floor irrelevant.
        if last and self.me == 1:
            return 0.0

        frac = 0.90 - 0.55 * (p ** 1.22)  # ~0.90 -> ~0.35
        frac = max(0.38, min(0.92, frac))
        if last and self.me == 0:
            frac = min(frac, 0.33)  # final proposal (as first): be closable

        floor = frac * self.total
        # Don't crater below best_seen too early.
        floor = max(floor, self.best_seen - (0.06 + 0.14 * p) * self.total)
        return max(0.0, min(self.total, floor))

    def _accept_floor(self, p: float) -> float:
        if self.total <= 0:
            return 0.0
        frac = 0.84 - 0.62 * (p ** 1.10)
        min_frac = 0.25 if p < 0.90 else 0.14
        return max(min_frac, min(0.90, frac)) * self.total

    # ------------------------- candidate offers -------------------------

    def _build_greedy_ladder(self) -> List[Tuple[int, List[int]]]:
        # Ladder by conceding our lowest-value units first.
        off = self._base_ask()
        ladder = {(tuple(off)): self._my_value(off)}

        # Build unit list (one entry per unit) sorted by increasing our value loss.
        units = []
        for i in self.pos_idx:
            units.extend([i] * off[i])
        units.sort(key=lambda i: self.values[i])

        for i in units:
            if off[i] > 0:
                off = off.copy()
                off[i] -= 1
                ladder.setdefault(tuple(off), self._my_value(off))

        items = [(v, list(k)) for k, v in ladder.items()]
        items.sort(key=lambda t: t[0], reverse=True)
        return items

    def _candidate_subset(self, p: float, their_last: Optional[List[int]]) -> List[Tuple[int, List[int]]]:
        # Always include base ask + their_last (clamped) to encourage closure.
        cands = {}
        base = self._base_ask()
        cands[tuple(base)] = (self._my_value(base), base)

        if their_last is not None and self._valid_offer(their_last):
            tl = list(their_last)
            for i in self.zero_idx:
                tl[i] = 0
            if self._valid_offer(tl):
                cands[tuple(tl)] = (self._my_value(tl), tl)

        # Add a slice from precomputed offers, biased to high value early / wider late.
        # Limit count to keep particle scoring fast.
        want = int(900 + 650 * p)  # ~900 -> ~1550
        want = max(700, min(1700, want))

        if self._offers:
            # Take top band, and also a lower band late to ensure agreement options exist.
            top_take = min(len(self._offers), want)
            for mv, off in self._offers[:top_take]:
                cands[tuple(off)] = (mv, off)

            if p > 0.60:
                # add a modest tail (lower my-value offers) for closing
                tail = self._offers[min(len(self._offers), max(0, int(len(self._offers) * 0.15))):]
                step = max(1, len(tail) // 400)
                for mv, off in tail[::step]:
                    cands.setdefault(tuple(off), (mv, off))

        return list(cands.values())

    # ------------------------- opponent particles -------------------------

    def _init_particles(self, m: int) -> List[List[float]]:
        if self.total <= 0:
            return [[0.0] * self.n for _ in range(m)]

        parts = []
        for _ in range(m):
            # Mix of shapes to cover sparse and spread preferences.
            shape = self.rng.choice((0.35, 0.7, 1.0, 1.8))
            w = [0.0] * self.n
            for i in range(self.n):
                if self.counts[i] <= 0:
                    continue
                # Approx Dirichlet via expovariate; adjust by "shape".
                x = self.rng.expovariate(1.0) ** shape
                # Slight prior: our zero-valued items are plausible to be valuable to them.
                if self.values[i] == 0 and self.counts[i] > 0:
                    x *= 1.35
                w[i] = max(1e-9, x)

            denom = sum(self.counts[i] * w[i] for i in range(self.n))
            if denom <= 0:
                parts.append([0.0] * self.n)
            else:
                scale = self.total / denom
                parts.append([w[i] * scale for i in range(self.n)])
        return parts

    def _normalize_and_resample_if_needed(self):
        # Convert logw -> normalized weights, compute ESS, resample if degenerate.
        m = len(self.logw)
        mx = max(self.logw)
        ws = [math.exp(lw - mx) for lw in self.logw]
        s = sum(ws)
        if s <= 0:
            self.logw = [0.0] * m
            return

        ws = [w / s for w in ws]
        ess = 1.0 / sum(w * w for w in ws)

        if ess >= 0.55 * m:
            # keep as-is; compress logw for stability
            self.logw = [math.log(w + 1e-18) for w in ws]
            return

        # Systematic resampling
        step = 1.0 / m
        u0 = self.rng.random() * step
        c = ws[0]
        i = 0
        new_parts = []
        for j in range(m):
            u = u0 + j * step
            while u > c and i < m - 1:
                i += 1
                c += ws[i]
            new_parts.append(self.particles[i])
        self.particles = new_parts
        self.logw = [0.0] * m

    def _update_particles(self, their_offer_to_us: List[int], p: float, rejected_my_offer: Optional[List[int]]):
        if self.total <= 0 or not self.particles:
            return

        thr = self._their_threshold(p)
        scale = max(1.0, 0.10 * self.total)

        # Likelihood: they tend to offer us items they (on average) value less.
        # Opponent value of THEIR share = total - dot(mu, offer_to_us).
        # So low dot(mu, offer_to_us) => more likely.
        k_offer = 5.0 + 3.0 * (1.0 - p)  # stronger early

        # Rejection likelihood: if they rejected our last offer, then (under that particle)
        # their value from our offer should be below their threshold.
        k_rej = 7.0

        for idx, mu in enumerate(self.particles):
            dot_offer = 0.0
            for i in range(self.n):
                dot_offer += mu[i] * their_offer_to_us[i]
            ll = -k_offer * (dot_offer / max(1e-9, self.total))

            if rejected_my_offer is not None:
                dot_mine = 0.0
                for i in range(self.n):
                    dot_mine += mu[i] * rejected_my_offer[i]
                tv = self.total - dot_mine
                gap = tv - thr
                if gap > 0:
                    ll -= k_rej * (gap / scale)

            self.logw[idx] += ll

        self._normalize_and_resample_if_needed()

    # ------------------------- acceptance probability -------------------------

    def _p_accept(self, offer_to_us: List[int], p: float) -> float:
        # Estimated probability opponent accepts OUR proposed offer (their share meets threshold).
        thr = self._their_threshold(p)
        scale = max(1.0, 0.10 * self.total)
        mx = max(self.logw) if self.logw else 0.0
        ws = [math.exp(lw - mx) for lw in self.logw] if self.logw else [1.0] * len(self.particles)
        s = sum(ws) or 1.0

        acc = 0.0
        for w, mu in zip(ws, self.particles):
            dot_mine = 0.0
            for i in range(self.n):
                dot_mine += mu[i] * offer_to_us[i]
            tv = self.total - dot_mine
            acc += w * self._sigmoid((tv - thr) / scale)
        return acc / s

    # ------------------------- choose counter -------------------------

    def _pick_counter(self, their_last: Optional[List[int]]) -> List[int]:
        p = self._progress()
        last = self._is_last_our_turn()
        my_floor = self._my_floor(p)

        # Monotone concession: don't increase our demanded value later (tiny slack).
        max_mv = None
        if self.last_ask_value is not None and p > 0.10:
            max_mv = self.last_ask_value + int(0.01 * self.total)

        best_off = None
        best_score = -1e100
        best_pacc = 0.0

        # Candidate set
        cands = self._candidate_subset(p, their_last)

        # Late: allow offers below floor to avoid no-deal; early: insist on floor.
        for mv, off in cands:
            if not last and mv + 1e-9 < my_floor:
                continue
            if max_mv is not None and mv > max_mv:
                continue

            # Always enforce giving away our zero-value items.
            if any(off[i] != 0 for i in self.zero_idx):
                off = off.copy()
                for i in self.zero_idx:
                    off[i] = 0
                mv = self._my_value(off)

            pacc = self._p_accept(off, p)

            # Distance to their last offer (from our perspective) for "reasonable" movement.
            dist = 0.0
            if their_last is not None and self._valid_offer(their_last):
                dist = sum(abs(off[i] - their_last[i]) for i in range(self.n)) / self.sum_counts

            # Score: maximize expected value, with small anchoring term early.
            if p < 0.70:
                score = mv * (pacc + 0.10 * (1.0 - p)) + 0.10 * self.total * pacc - 0.035 * self.total * dist
            else:
                score = mv * pacc + 0.22 * self.total * pacc - 0.040 * self.total * dist

            if last and self.me == 0:
                # Final proposal: prioritize closure.
                score = mv * pacc + 0.30 * self.total * pacc - 0.055 * self.total * dist

            if score > best_score:
                best_score = score
                best_off = off
                best_pacc = pacc

        if best_off is None:
            best_off = self._base_ask()
            best_pacc = self._p_accept(best_off, p)

        self._last_pick_pacc = best_pacc
        return list(best_off)

    # ------------------------- main API -------------------------

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        # If everything worthless, accept any valid offer; otherwise ask for 0.
        if self.total <= 0:
            self.turn += 1
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        p = self._progress()
        last = self._is_last_our_turn()

        # Handle incoming offer
        if o is not None:
            if not self._valid_offer(o):
                # Invalid -> respond with a sane counter
                counter = self._pick_counter(self.their_last)
                self.my_last_offer = counter
                self.last_ask_value = self._my_value(counter)
                self.turn += 1
                return counter

            # Update particles: their offer arrives after they rejected our previous offer (if any).
            self._update_particles(o, p, rejected_my_offer=self.my_last_offer)

            self.their_last = list(o)
            myv = self._my_value(o)
            self.best_seen = max(self.best_seen, myv)

            # If we're second and it's our last turn, counter can't be accepted.
            if last and self.me == 1:
                self.turn += 1
                return None

            # Strong offers: accept immediately.
            if myv >= 0.72 * self.total:
                self.turn += 1
                return None

            # Late: avoid no-deal if it's at least something.
            if p > 0.93 and myv >= 0.12 * self.total:
                self.turn += 1
                return None

            # Decide accept vs counter using expected value.
            counter = self._pick_counter(self.their_last)
            cv = self._my_value(counter)
            pacc = self._last_pick_pacc
            ev = cv * pacc  # expected value from counter (0 if rejected and no deal)

            req = max(self._accept_floor(p), self._my_floor(p) - 0.06 * self.total)

            if myv + 1e-9 >= req:
                self.turn += 1
                return None

            # Accept if counter doesn't beat it by enough (risk-adjusted).
            # Early: demand more improvement; late: accept close calls.
            margin = (0.06 - 0.04 * p) * self.total
            if myv >= ev - margin:
                self.turn += 1
                return None

            # Counter
            self.my_last_offer = counter
            self.last_ask_value = cv
            self.turn += 1
            return counter

        # We start (o is None): propose
        counter = self._pick_counter(self.their_last)
        self.my_last_offer = counter
        self.last_ask_value = self._my_value(counter)
        self.turn += 1
        return counter