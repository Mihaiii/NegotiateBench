import math
import random


class Agent:
    """
    Belief-sampling haggling agent.

    Key features vs the provided code:
    - Robustly handles the common "offer means what the speaker keeps" convention by inferring
      whether incoming offers are already "our share" or need to be complemented (counts - offer).
    - Keeps internal representation as "our share" (what we get/keep).
    - Particle belief over opponent unit-values scaled to match the known total value constraint.
    - Updates belief from opponent offers and from their rejection of our last offer.
    - Generates candidates from a fast ratio-greedy concession path + random concessions + tweaks
      around their last offer; chooses offer maximizing my_value * P(accept) with time pressure.
    """

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_int = sum(c * v for c, v in zip(self.counts, self.values))
        self.total = float(self.total_int)

        # Our decision index (0..max_rounds-1)
        self.t = 0

        # Best offer value we've seen for us (incoming).
        self.best_seen = 0

        # Opponent offer interpretation mode:
        # - None: unknown, infer at first incoming offer
        # - "as_is": incoming o is already our share
        # - "complement": incoming o is opponent share / speaker-keeps, so our share is counts - o
        self._mode = None

        # Last offer we sent (our share), for rejection update.
        self.last_sent = None

        # Deterministic RNG seed.
        seed = (sum(self.counts) * 1000003 + sum(self.values) * 9176 +
                self.max_rounds * 131 + self.me * 7) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        self.particles, self.weights = self._init_particles(m=220)

    # ----------------------------- helpers -----------------------------

    def _valid_offer(self, o) -> bool:
        if not isinstance(o, list) or len(o) != self.n:
            return False
        for i, x in enumerate(o):
            if not isinstance(x, int):
                return False
            if x < 0 or x > self.counts[i]:
                return False
        return True

    def _my_value(self, my_share: list[int]) -> int:
        return sum(v * x for v, x in zip(self.values, my_share))

    def _global_progress(self) -> float:
        """Progress in [0,1] across the whole game timeline (both players' turns)."""
        if self.max_rounds <= 1:
            return 1.0
        denom = (2 * self.max_rounds - 1)
        # Our move index occurs at time 2*t + me (me==1 means we act second in each round).
        g = (2 * self.t + self.me) / denom
        if g < 0.0:
            return 0.0
        if g > 1.0:
            return 1.0
        return g

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z <= -30.0:
            return 0.0
        if z >= 30.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    def _to_my_share(self, o_raw: list[int]) -> list[int]:
        """
        Interpret incoming offer list as our share.

        Many environments use "offer = what the speaker keeps".
        The prompt text says "offer = what you get".
        We infer which is being used from the first incoming offer by plausibility.
        """
        if self._mode is None:
            # Two hypotheses:
            as_is = o_raw
            comp = [self.counts[i] - o_raw[i] for i in range(self.n)]
            va = self._my_value(as_is)
            vb = self._my_value(comp)

            # Heuristic: opponents rarely open by gifting us ~all our total value.
            # If interpreting "as_is" yields an implausibly generous deal, flip.
            if va > 0.75 * self.total and vb < va:
                self._mode = "complement"
            # Also, if "as_is" gives us literally everything (common greedy opening in speaker-keeps),
            # then complement is almost certainly correct.
            elif all(o_raw[i] == self.counts[i] for i in range(self.n)):
                self._mode = "complement"
            else:
                self._mode = "as_is"

        if self._mode == "as_is":
            return o_raw[:]
        # complement mode
        return [self.counts[i] - o_raw[i] for i in range(self.n)]

    def _opp_share(self, my_share: list[int]) -> list[int]:
        return [self.counts[i] - my_share[i] for i in range(self.n)]

    # -------------------------- belief particles ------------------------

    def _scaled_from_weights(self, w: list[float]) -> list[float]:
        denom = 0.0
        for i in range(self.n):
            denom += self.counts[i] * w[i]
        if denom <= 1e-12 or self.total <= 0.0:
            return [0.0] * self.n
        s = self.total / denom
        return [max(0.0, wi * s) for wi in w]

    def _init_particles(self, m: int = 220):
        if self.total <= 0.0:
            return [[0.0] * self.n], [1.0]

        parts = []
        eps = 1e-6

        # "Mostly one type matters" extremes.
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            parts.append(self._scaled_from_weights(w))

        # Uniform-ish.
        parts.append(self._scaled_from_weights([1.0] * self.n))

        # Random smooth particles.
        while len(parts) < m:
            w = []
            for _ in range(self.n):
                u = self.rng.random()
                w.append(-math.log(max(1e-12, u)))  # Exp(1)
            parts.append(self._scaled_from_weights(w))

        wts = [1.0 / len(parts)] * len(parts)
        return parts, wts

    def _renormalize(self) -> None:
        s = sum(self.weights)
        if not (s > 0.0) or math.isnan(s) or math.isinf(s):
            k = len(self.weights)
            self.weights = [1.0 / k] * k
            return
        inv = 1.0 / s
        self.weights = [w * inv for w in self.weights]

    def _mean_opp_unit(self) -> list[float]:
        mu = [0.0] * self.n
        for w, u in zip(self.weights, self.particles):
            for i in range(self.n):
                mu[i] += w * u[i]
        return mu

    # -------------------------- belief updates --------------------------

    def _update_from_their_offer(self, my_share: list[int]) -> None:
        """They proposed this split; likely they keep items they value."""
        if self.total <= 0.0:
            return

        beta = 5.5
        opp = self._opp_share(my_share)

        for k, u in enumerate(self.particles):
            keep_val = 0.0
            for i in range(self.n):
                keep_val += opp[i] * u[i]
            # Margin is positive if they keep > half their value.
            margin = (2.0 * keep_val - self.total) / (self.total + 1e-12)
            like = self._sigmoid(beta * margin)
            self.weights[k] *= 0.12 + 0.88 * like

        self._renormalize()

    def _opp_threshold_frac(self, p: float) -> float:
        # Opponent acceptance threshold prior; decays over time.
        # Slightly firmer early than the old code; still drops to a deal-friendly level.
        return 0.76 - 0.51 * p  # 0.76 -> 0.25

    def _update_from_rejection_of_last(self) -> None:
        """If they made a new offer, they rejected our previous one; penalize particles that imply acceptance."""
        if self.last_sent is None or self.total <= 0.0:
            return

        p = self._global_progress()
        theta = self._opp_threshold_frac(p) * self.total
        kscale = 0.085 * self.total + 1e-9
        gamma = 1.35

        opp = self._opp_share(self.last_sent)
        for idx, u in enumerate(self.particles):
            keep_val = 0.0
            for i in range(self.n):
                keep_val += opp[i] * u[i]
            p_accept = self._sigmoid((keep_val - theta) / kscale)
            rej_like = max(1e-6, 1.0 - p_accept)
            self.weights[idx] *= rej_like ** gamma

        self._renormalize()

    # ------------------------- accept / concede -------------------------

    def _is_last_our_turn(self) -> bool:
        return self.t >= self.max_rounds - 1

    def _my_floor(self) -> float:
        if self.total <= 0.0:
            return 0.0

        p = self._global_progress()
        last = self._is_last_our_turn()

        # If we are second on our last turn, counter-offer can't be accepted (no more turns),
        # so accept anything valid.
        if last and self.me == 1:
            return 0.0

        # Concession schedule.
        frac = 0.92 - 0.62 * p  # 0.92 -> 0.30

        # If we are first and it's our final chance to propose, allow a bit lower to close.
        if last and self.me == 0:
            frac = min(frac, 0.20)

        floor = frac * self.total

        # Don't collapse far below best seen unless quite late.
        floor = max(floor, self.best_seen - (0.10 + 0.22 * p) * self.total)

        # Avoid accepting tiny deals in non-terminal situations.
        floor = max(floor, 0.14 * self.total)

        if floor < 0.0:
            return 0.0
        if floor > self.total:
            return self.total
        return floor

    # --------------------- opponent acceptance model --------------------

    def _p_opp_accept(self, my_share: list[int]) -> float:
        if self.total <= 0.0:
            return 1.0

        p = self._global_progress()
        theta = self._opp_threshold_frac(p) * self.total
        kscale = 0.085 * self.total + 1e-9

        opp = self._opp_share(my_share)

        acc = 0.0
        for w, u in zip(self.weights, self.particles):
            keep_val = 0.0
            for i in range(self.n):
                keep_val += opp[i] * u[i]
            acc += w * self._sigmoid((keep_val - theta) / kscale)
        return acc

    # -------------------------- offer generation ------------------------

    def _base_take(self) -> list[int]:
        # Take all items we value positively; give away all zero-value items.
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _ratio_order(self, opp_mu: list[float]) -> list[int]:
        eps = 1e-9
        idxs = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        # Concede types where it's cheap to us and likely valuable to them (high opp_mu / our_value).
        idxs.sort(key=lambda i: opp_mu[i] / (self.values[i] + eps), reverse=True)
        return idxs

    def _greedy_to_value(self, target: float, opp_mu: list[float]) -> list[int]:
        """Start from base and concede 1 unit at a time guided by opp_mu/our_value until my_value<=target."""
        o = self._base_take()
        myv = self._my_value(o)
        if myv <= target:
            return o

        order = self._ratio_order(opp_mu)
        if not order:
            return o

        # Concede one unit at a time; bounded for safety.
        for _ in range(sum(self.counts) + 5):
            if myv <= target:
                break
            best_i = -1
            best_ratio = -1.0
            for i in order:
                if o[i] <= 0:
                    continue
                r = opp_mu[i] / (self.values[i] + 1e-9)
                if r > best_ratio:
                    best_ratio = r
                    best_i = i
            if best_i < 0:
                break
            o[best_i] -= 1
            myv -= self.values[best_i]

        return o

    def _path_concessions(self, opp_mu: list[float]) -> list[list[int]]:
        """Generate offers along a concession path (in units conceded)."""
        base = self._base_take()
        order = self._ratio_order(opp_mu)
        if not order:
            return [base]

        # Total units we could concede from base (only positive-value types included).
        total_units = sum(base[i] for i in range(self.n))

        # Steps: more dense early, sparser later.
        steps = [0, 1, 2, 3, 4, 6, 8, 10, 13, 16, 20, 25, 30, 36, 45, 60, 80, 110]
        steps = [k for k in steps if k <= total_units]
        if steps and steps[-1] != total_units:
            steps.append(total_units)

        offers = []
        for k in steps:
            o = base[:]
            left = k
            # Concede k units following order cyclically (so we don't dump all of one type only).
            # This keeps offers "smooth" and often more acceptable.
            j = 0
            while left > 0 and j < 100000:
                i = order[j % len(order)]
                if o[i] > 0:
                    o[i] -= 1
                    left -= 1
                j += 1
            offers.append(o)

        return offers

    def _random_offer(self, opp_mu: list[float]) -> list[int]:
        """Random concession offer biased toward giving opponent high opp_mu/our_value items, increasing with time."""
        p = self._global_progress()
        o = self._base_take()
        eps = 1e-9

        for i in range(self.n):
            if o[i] <= 0:
                continue

            ratio = opp_mu[i] / (self.values[i] + eps)
            base = ratio / (1.0 + ratio)  # 0..1

            # Intensity increases with time.
            inten = (0.08 + 0.80 * p) * base

            r = self.rng.random()
            r = r ** (2.0 - 1.2 * p)  # earlier -> smaller, later -> larger
            give = int((inten * r) * (o[i] + 0.75))
            if give > 0:
                o[i] = max(0, o[i] - min(o[i], give))

        return o

    def _tweak_ask_more(self, their_my_share: list[int], k: int = 1) -> list[int]:
        """Ask for slightly more than their offer in our highest-value types."""
        o = their_my_share[:]
        # Always give away our zero-value items.
        for i in range(self.n):
            if self.values[i] <= 0:
                o[i] = 0

        idxs = list(range(self.n))
        idxs.sort(key=lambda i: self.values[i], reverse=True)
        for i in idxs:
            if self.values[i] <= 0:
                continue
            if o[i] < self.counts[i]:
                o[i] = min(self.counts[i], o[i] + k)
                break
        return o

    def _choose_counter(self, their_my_share: list[int] | None) -> list[int]:
        if self.total <= 0.0:
            return [0] * self.n

        p = self._global_progress()
        floor = self._my_floor()
        opp_mu = self._mean_opp_unit()
        last = self._is_last_our_turn()

        cand = {}
        def add(x):
            if self._valid_offer(x):
                cand[tuple(x)] = x

        # Value targets: anchor high early, drift toward floor.
        high = max(floor, (0.98 - 0.25 * p) * self.total)
        for s in (0.0, 0.06, 0.12, 0.20, 0.30, 0.42):
            tgt = max(floor, high - s * self.total)
            add(self._greedy_to_value(tgt, opp_mu))

        # Concession path (fast Pareto-ish set).
        for off in self._path_concessions(opp_mu):
            add(off)

        # Random exploration (less near the end for stability).
        n_rand = 65 if p < 0.7 else 40
        for _ in range(n_rand):
            add(self._random_offer(opp_mu))

        # Include their offer (as our-share) and small tweaks.
        if their_my_share is not None:
            add(their_my_share)
            add(self._tweak_ask_more(their_my_share, k=1))
            if p < 0.8:
                add(self._tweak_ask_more(their_my_share, k=2))

        # Score candidates.
        best = None
        best_score = -1e100

        for off in cand.values():
            myv = self._my_value(off)

            # Enforce our floor unless we must accept/can't counter (handled elsewhere).
            if myv + 1e-9 < floor and not (last and self.me == 1):
                continue

            pacc = self._p_opp_accept(off)

            # Time pressure: late game emphasizes closing probability.
            w = 0.48 + 0.44 * p
            # Use a mildly concave transform early; closer to linear late.
            pterm = pacc ** (0.85 - 0.35 * p)

            score = myv * ((1.0 - w) + w * pterm)

            # Late bonus for "very likely" closers.
            score += (0.015 + 0.06 * p) * self.total * pacc

            if score > best_score:
                best_score = score
                best = off

        if best is None:
            best = self._base_take()

        self.last_sent = best[:]
        return best

    # -------------------------------- API --------------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Degenerate: nothing is worth anything to us.
        if self.total_int <= 0:
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        last = self._is_last_our_turn()

        # Process incoming offer (if any).
        their_my_share = None
        if o is not None:
            if not self._valid_offer(o):
                # Reply safely with a valid counter.
                counter = self._choose_counter(None)
                self.t += 1
                return counter

            their_my_share = self._to_my_share(o)
            myv = self._my_value(their_my_share)
            if myv > self.best_seen:
                self.best_seen = myv

            # If this is a new opponent offer, they rejected our previous offer (if any).
            self._update_from_rejection_of_last()
            self._update_from_their_offer(their_my_share)

            # If we are second on our final turn, never counter (a counter cannot be accepted).
            if last and self.me == 1:
                self.t += 1
                return None

            # Standard accept rule.
            if myv + 1e-9 >= self._my_floor():
                self.t += 1
                return None

            # Late-game extra safety: accept solid offers that are likely to close anyway.
            if self._global_progress() > 0.78:
                if myv >= 0.40 * self.total and self._p_opp_accept(their_my_share) > 0.94:
                    self.t += 1
                    return None
        else:
            # We start the negotiation.
            self.last_sent = None

        counter = self._choose_counter(their_my_share)
        self.t += 1
        return counter