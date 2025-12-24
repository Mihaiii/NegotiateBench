import math
import random


class Agent:
    """
    Offer protocol:
      - Incoming offer o: opponent proposes OUR share (list of ints).
      - Return None to accept (only if o is not None).
      - Return list to counter: OUR desired share.
    """

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))
        self.sum_counts = max(1, sum(self.counts))

        self.step = 0  # our call index: 0..max_rounds-1
        self.best_seen = 0

        self.pos_idx = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        self.zero_idx = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] == 0]

        self.opp_last = None
        self.my_last = None
        self.last_ask_value = None

        # Precompute a concession ladder (always), and optionally full enumeration if small.
        self.ladder = self._build_ladder()
        self.all_offers = None
        self._init_offer_space()

        # Opponent modeling: particles over per-unit values mu, scaled so sum(counts*mu)=total.
        self.rng = random.Random(1337)
        self.P = 140 if self.n <= 7 else 120
        self.particles = self._init_particles(self.P)
        self.logw = [0.0] * len(self.particles)

    # ------------------------- basics -------------------------

    def _valid_offer(self, o) -> bool:
        if not isinstance(o, (list, tuple)) or len(o) != self.n:
            return False
        for i, x in enumerate(o):
            if not isinstance(x, int) or x < 0 or x > self.counts[i]:
                return False
        return True

    def _my_value(self, share: list[int]) -> int:
        return sum(self.values[i] * share[i] for i in range(self.n))

    def _is_last_our_turn(self) -> bool:
        return self.step >= self.max_rounds - 1

    def _progress(self) -> float:
        # Global turn index when we act: 0..(2R-1).
        if self.max_rounds <= 1:
            return 1.0
        overall = 2 * self.step + self.me
        return max(0.0, min(1.0, overall / (2 * self.max_rounds - 1)))

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x <= -35.0:
            return 0.0
        if x >= 35.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-x))

    def _base_ask(self) -> list[int]:
        # Keep everything that is positive value; always give away our zero-value types.
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _enforce_zero_giveaway(self, off: list[int]) -> list[int]:
        if not self.zero_idx:
            return off
        off = list(off)
        for i in self.zero_idx:
            off[i] = 0
        return off

    # ------------------------- thresholds -------------------------

    def _their_threshold(self, p: float) -> float:
        # Estimated opponent minimum value for THEIR share (in their units).
        # Decreases with time.
        frac = 0.84 - 0.64 * (p ** 1.05)  # ~0.84 -> ~0.20
        return max(0.18, min(0.88, frac)) * self.total

    def _my_demand(self, p: float) -> float:
        if self.total <= 0:
            return 0.0
        last = self._is_last_our_turn()
        frac = 0.93 - 0.60 * (p ** 1.18)  # ~0.93 -> ~0.33
        frac = max(0.36, min(0.95, frac))
        if last and self.me == 0:
            frac = min(frac, 0.30)  # final proposal as first: make it closable
        # Keep from dropping absurdly below our best seen too early.
        floor = frac * self.total
        floor = max(floor, self.best_seen - (0.05 + 0.12 * p) * self.total)
        return max(0.0, min(self.total, floor))

    def _accept_floor(self, p: float) -> float:
        if self.total <= 0:
            return 0.0
        frac = 0.90 - 0.70 * (p ** 1.08)  # ~0.90 -> ~0.20
        # Very late, allow a bit more flexibility to avoid no-deal.
        min_frac = 0.18 if p < 0.92 else 0.08
        return max(min_frac, min(0.92, frac)) * self.total

    # ------------------------- offer space -------------------------

    def _build_ladder(self):
        base = self._base_ask()
        base = self._enforce_zero_giveaway(base)
        ladder = [base]

        # Concede units in order of increasing our per-unit value.
        units = []
        for i in self.pos_idx:
            units.extend([i] * base[i])
        units.sort(key=lambda i: (self.values[i], -self.counts[i]))

        cur = base
        for i in units:
            if cur[i] <= 0:
                continue
            nxt = cur.copy()
            nxt[i] -= 1
            ladder.append(nxt)
            cur = nxt

        # Deduplicate while preserving order, and store with my_value.
        seen = set()
        out = []
        for off in ladder:
            t = tuple(off)
            if t in seen:
                continue
            seen.add(t)
            out.append((self._my_value(off), off))
        out.sort(key=lambda x: x[0], reverse=True)
        return out

    def _init_offer_space(self):
        # If full cartesian space is small, enumerate all offers (for candidate sampling).
        max_space = 220_000
        space = 1
        for c in self.counts:
            space *= (c + 1)
            if space > max_space:
                break
        if self.total <= 0 or space > max_space:
            self.all_offers = None
            return

        offers = []
        cur = [0] * self.n

        def rec(k: int):
            if k == self.n:
                off = self._enforce_zero_giveaway(cur)
                offers.append((self._my_value(off), off.copy()))
                return
            for x in range(self.counts[k] + 1):
                cur[k] = x
                rec(k + 1)

        rec(0)
        # Dedup + sort
        ded = {}
        for v, off in offers:
            ded[tuple(off)] = v
        self.all_offers = [(v, list(k)) for k, v in ded.items()]
        self.all_offers.sort(key=lambda x: x[0], reverse=True)

    # ------------------------- opponent particles -------------------------

    def _init_particles(self, m: int):
        if self.total <= 0:
            return [[0.0] * self.n for _ in range(m)]

        parts = []
        for _ in range(m):
            shape = self.rng.choice((0.45, 0.8, 1.2, 2.0))
            w = [0.0] * self.n
            for i in range(self.n):
                if self.counts[i] <= 0:
                    continue
                x = (self.rng.expovariate(1.0) ** shape) + 1e-9
                # Prior: our zero-valued types slightly more likely to matter to them.
                if self.values[i] == 0 and self.counts[i] > 0:
                    x *= 1.25
                w[i] = x
            denom = sum(self.counts[i] * w[i] for i in range(self.n))
            if denom <= 0:
                parts.append([0.0] * self.n)
            else:
                scale = self.total / denom
                parts.append([w[i] * scale for i in range(self.n)])
        return parts

    def _norm_weights(self):
        if not self.particles:
            return []
        mx = max(self.logw)
        ws = [math.exp(lw - mx) for lw in self.logw]
        s = sum(ws) or 1.0
        return [w / s for w in ws]

    def _resample_if_needed(self):
        m = len(self.particles)
        if m <= 1:
            return
        ws = self._norm_weights()
        ess = 1.0 / sum(w * w for w in ws)
        if ess >= 0.60 * m:
            # store normalized in log-space to avoid drift
            self.logw = [math.log(w + 1e-18) for w in ws]
            return

        # systematic resampling
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

    def _update_particles(self, their_offer_to_us: list[int], p: float, rejected_my_offer: list[int] | None):
        if self.total <= 0 or not self.particles:
            return

        thr = self._their_threshold(p)
        scale = max(1.0, 0.10 * self.total)

        # Likelihood pieces:
        #  1) They tend to give us items they value less: smaller dot(mu, offer_to_us) is likelier.
        #  2) Their offered split should still give them something near/above their threshold.
        k_give = 6.0 + 3.0 * (1.0 - p)
        k_below = 10.0

        # Rejection: if they rejected our previous offer, then (under that particle)
        # their value from our offer should be below their threshold (or close).
        k_rej = 9.0

        for idx, mu in enumerate(self.particles):
            dot_offer = 0.0
            for i in range(self.n):
                dot_offer += mu[i] * their_offer_to_us[i]
            keep_offer = self.total - dot_offer

            ll = -k_give * (dot_offer / max(1e-9, self.total))
            # Penalize particles where their offered deal would undercut their own threshold.
            if keep_offer < thr:
                ll -= k_below * ((thr - keep_offer) / scale)

            if rejected_my_offer is not None:
                dot_mine = 0.0
                for i in range(self.n):
                    dot_mine += mu[i] * rejected_my_offer[i]
                keep_from_mine = self.total - dot_mine
                # If particle says they should have been happy, penalize.
                if keep_from_mine > thr:
                    ll -= k_rej * ((keep_from_mine - thr) / scale)

            self.logw[idx] += ll

        self._resample_if_needed()

    # ------------------------- acceptance probability -------------------------

    def _mean_mu(self):
        ws = self._norm_weights()
        if not ws:
            return [0.0] * self.n
        mm = [0.0] * self.n
        for w, mu in zip(ws, self.particles):
            for i in range(self.n):
                mm[i] += w * mu[i]
        return mm

    def _p_accept_full(self, offer_to_us: list[int], p: float) -> float:
        thr = self._their_threshold(p)
        scale = max(1.0, 0.10 * self.total)
        ws = self._norm_weights()
        if not ws:
            ws = [1.0 / max(1, len(self.particles))] * len(self.particles)

        acc = 0.0
        for w, mu in zip(ws, self.particles):
            dot_mine = 0.0
            for i in range(self.n):
                dot_mine += mu[i] * offer_to_us[i]
            keep = self.total - dot_mine
            acc += w * self._sigmoid((keep - thr) / scale)
        return acc

    def _p_accept_mean(self, offer_to_us: list[int], p: float, mean_mu: list[float]) -> float:
        thr = self._their_threshold(p)
        scale = max(1.0, 0.10 * self.total)
        dot_mine = 0.0
        for i in range(self.n):
            dot_mine += mean_mu[i] * offer_to_us[i]
        keep = self.total - dot_mine
        return self._sigmoid((keep - thr) / scale)

    # ------------------------- candidate generation -------------------------

    def _candidates(self, p: float, opp_last: list[int] | None) -> list[tuple[int, list[int]]]:
        # Build a compact candidate set (deduplicated).
        cand = {}
        def add(off: list[int]):
            off = self._enforce_zero_giveaway(off)
            if not self._valid_offer(off):
                return
            t = tuple(off)
            if t not in cand:
                cand[t] = self._my_value(off)

        base = self._base_ask()
        add(base)

        if opp_last is not None and self._valid_offer(opp_last):
            add(list(opp_last))

        if self.my_last is not None and opp_last is not None and self._valid_offer(opp_last):
            mid = [min(self.counts[i], max(0, (self.my_last[i] + opp_last[i]) // 2)) for i in range(self.n)]
            add(mid)

        # Take a slice from ladder / all_offers depending on time.
        take_top = int(450 + 950 * (1.0 - p))  # early: more top offers
        take_top = max(300, min(1300, take_top))

        if self.all_offers is not None:
            for mv, off in self.all_offers[:take_top]:
                add(off)
            # late: add some lower offers for closing
            if p > 0.55:
                tail = self.all_offers[int(len(self.all_offers) * 0.20):]
                step = max(1, len(tail) // 350)
                for mv, off in tail[::step]:
                    add(off)
        else:
            for mv, off in self.ladder[:take_top]:
                add(off)
            if p > 0.60:
                tail = self.ladder[int(len(self.ladder) * 0.20):]
                step = max(1, len(tail) // 250)
                for mv, off in tail[::step]:
                    add(off)

        # Random perturbations (help escape pathological ladders).
        # Give away low-value units with higher probability.
        if self.pos_idx:
            weights = [1.0 / (1.0 + self.values[i]) for i in range(self.n)]
            trials = 120 if p < 0.75 else 200
            max_give = 1 + int((0.20 + 0.45 * p) * self.sum_counts / max(1, self.n))
            for _ in range(trials):
                off = base.copy()
                g = self.rng.randint(1, max(1, max_give))
                for _ in range(g):
                    i = self._weighted_choice(weights)
                    if off[i] > 0 and self.values[i] > 0:
                        off[i] -= 1
                add(off)

        out = [(mv, list(k)) for k, mv in cand.items()]
        out.sort(key=lambda x: x[0], reverse=True)
        return out

    def _weighted_choice(self, weights):
        s = 0.0
        for w in weights:
            s += max(0.0, w)
        if s <= 0:
            return self.rng.randrange(self.n)
        r = self.rng.random() * s
        acc = 0.0
        for i, w in enumerate(weights):
            acc += max(0.0, w)
            if acc >= r:
                return i
        return self.n - 1

    # ------------------------- pick counter -------------------------

    def _pick_counter(self, opp_last: list[int] | None) -> list[int]:
        p = self._progress()
        last = self._is_last_our_turn()
        my_floor = self._my_demand(p)

        # Monotone concession (after a little warmup).
        max_mv = None
        if self.last_ask_value is not None and p > 0.08:
            max_mv = self.last_ask_value + int(0.01 * self.total)

        mean_mu = self._mean_mu()
        cands = self._candidates(p, opp_last)

        # Stage 1: cheap scoring using mean mu; keep top few for full particle scoring.
        short = []
        dist_base = 0.04 * self.total if p < 0.7 else 0.06 * self.total

        for mv, off in cands:
            if not last and mv + 1e-9 < my_floor:
                continue
            if max_mv is not None and mv > max_mv:
                continue

            pacc_est = self._p_accept_mean(off, p, mean_mu)

            dist = 0.0
            if opp_last is not None and self._valid_offer(opp_last):
                dist = sum(abs(off[i] - opp_last[i]) for i in range(self.n)) / self.sum_counts

            # Encourage closure later; earlier prefer value.
            if p < 0.70:
                score = mv * (0.20 + 0.80 * pacc_est) - dist_base * dist
            else:
                score = mv * (0.10 + 0.90 * pacc_est) + 0.18 * self.total * pacc_est - dist_base * dist

            if last and self.me == 0:
                score = mv * (0.05 + 0.95 * pacc_est) + 0.25 * self.total * pacc_est - (dist_base * 1.15) * dist

            short.append((score, mv, off))

        if not short:
            return self._enforce_zero_giveaway(self._base_ask())

        short.sort(reverse=True, key=lambda x: x[0])
        short = short[:80]

        best = None
        best_score = -1e100
        for _, mv, off in short:
            pacc = self._p_accept_full(off, p)
            dist = 0.0
            if opp_last is not None and self._valid_offer(opp_last):
                dist = sum(abs(off[i] - opp_last[i]) for i in range(self.n)) / self.sum_counts

            score = mv * pacc + (0.10 + 0.18 * p) * self.total * pacc - (0.05 * self.total) * dist
            if last and self.me == 0:
                score = mv * pacc + 0.28 * self.total * pacc - (0.06 * self.total) * dist

            if score > best_score:
                best_score = score
                best = off

        return list(best)

    # ------------------------- main API -------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # If everything is worthless to us, accept any valid offer (or propose 0).
        if self.total <= 0:
            self.step += 1
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        p = self._progress()
        last = self._is_last_our_turn()

        # Incoming offer
        if o is not None:
            if not self._valid_offer(o):
                # Invalid opponent offer: respond with something valid.
                counter = self._pick_counter(self.opp_last)
                counter = self._enforce_zero_giveaway(counter)
                self.my_last = counter
                self.last_ask_value = self._my_value(counter)
                self.step += 1
                return counter

            o = self._enforce_zero_giveaway(list(o))
            myv = self._my_value(o)
            self.best_seen = max(self.best_seen, myv)

            # Update beliefs: they made o after rejecting our last offer (if any).
            self._update_particles(o, p, rejected_my_offer=self.my_last)

            self.opp_last = o

            # If it's our final action and we're second, we cannot make a meaningful counter:
            # returning a list would be "last word is counter" => no deal. So accept.
            if last and self.me == 1:
                self.step += 1
                return None

            # Immediate accept if clearly good.
            if myv >= 0.80 * self.total:
                self.step += 1
                return None

            # Compute a candidate counter and compare expected value.
            counter = self._pick_counter(self.opp_last)
            counter = self._enforce_zero_giveaway(counter)
            cv = self._my_value(counter)
            pacc = self._p_accept_full(counter, p)
            ev = cv * pacc

            req = self._accept_floor(p)
            # Late: don't die on a small difference.
            margin = (0.08 - 0.06 * p) * self.total

            # Accept rule: meet floor, or close to our best option's EV.
            if myv + 1e-9 >= req or myv >= ev - margin:
                self.step += 1
                return None

            # Otherwise counter.
            self.my_last = counter
            self.last_ask_value = cv
            self.step += 1
            return counter

        # We start (o is None): must propose an offer list.
        counter = self._pick_counter(self.opp_last)
        counter = self._enforce_zero_giveaway(counter)
        self.my_last = counter
        self.last_ask_value = self._my_value(counter)
        self.step += 1
        return counter