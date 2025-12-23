import math
import random


class Agent:
    """
    Belief-sampling negotiation agent.

    Core ideas:
    - Maintain a weighted particle set of opponent unit-values (floats) scaled so opponent total == our total.
    - Update particle weights from:
        (a) opponent offers (they tend to keep what they value),
        (b) rejection of our previous offer (their kept value was likely below their threshold).
    - Generate a moderate set of candidate counter-offers (greedy + random + tweaks),
      pick the one maximizing expected utility (my_value * P_accept).
    - Time-aware concession and endgame safety: if we are second on the last turn, always accept.
    """

    # ------------------------------- init -------------------------------

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_int = sum(c * v for c, v in zip(self.counts, self.values))
        self.total = float(self.total_int)

        self.t = 0  # our turn index: 0..max_rounds-1
        self.best_seen = 0

        seed = (sum(self.counts) * 1000003 + sum(self.values) * 9176 + self.max_rounds * 131 + self.me * 7) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        # Last offer we SENT (to us), used for "they rejected it" update.
        self.last_sent = None

        # Particle belief over opponent unit-values (floats), scaled to match total.
        self.particles, self.weights = self._init_particles(m=260)

    # ------------------------------ basics -----------------------------

    def _valid_offer(self, o) -> bool:
        if not isinstance(o, list) or len(o) != self.n:
            return False
        for i, x in enumerate(o):
            if not isinstance(x, int):
                return False
            if x < 0 or x > self.counts[i]:
                return False
        return True

    def _my_value(self, offer_to_me: list[int]) -> int:
        return sum(v * x for v, x in zip(self.values, offer_to_me))

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        p = self.t / (self.max_rounds - 1)
        if p < 0.0:
            return 0.0
        if p > 1.0:
            return 1.0
        return p

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z <= -30.0:
            return 0.0
        if z >= 30.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    # -------------------------- belief particles ------------------------

    def _scaled_from_weights(self, w: list[float]) -> list[float]:
        denom = 0.0
        for i in range(self.n):
            denom += self.counts[i] * w[i]
        if denom <= 1e-12 or self.total <= 0.0:
            return [0.0] * self.n
        s = self.total / denom
        return [max(0.0, wi * s) for wi in w]

    def _init_particles(self, m: int = 260):
        if self.total <= 0.0:
            # Degenerate: nothing matters to either side.
            return [[0.0] * self.n], [1.0]

        parts = []

        # Extreme-ish particles: opponent mostly values one type.
        eps = 1e-6
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            parts.append(self._scaled_from_weights(w))

        # Uniform-ish.
        parts.append(self._scaled_from_weights([1.0] * self.n))

        # Random smooth particles (exponential weights).
        # Keep count moderate for speed; 260 is plenty.
        while len(parts) < m:
            w = []
            for _ in range(self.n):
                u = self.rng.random()
                # Exponential(1) via -log(U)
                w.append(-math.log(max(1e-12, u)))
            parts.append(self._scaled_from_weights(w))

        wts = [1.0 / len(parts)] * len(parts)
        return parts, wts

    def _renormalize(self) -> None:
        # Normalize weights; if collapse, reset to uniform.
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

    def _update_from_their_offer(self, offer_to_me: list[int]) -> None:
        """
        They propose offer_to_me; opponent keeps counts - offer_to_me.
        Likelihood: higher when kept-value > given-value (they keep what they value).
        """
        if self.total <= 0.0:
            return

        beta = 5.0  # strength; moderate to avoid overfitting bluffs
        for k, u in enumerate(self.particles):
            # Opponent keep value = total - value_of_items_given_to_us (under this u)
            give_val = 0.0
            for i in range(self.n):
                give_val += offer_to_me[i] * u[i]
            keep_val = self.total - give_val
            # keep_val - give_val = 2*keep - total
            margin = (2.0 * keep_val - self.total) / (self.total + 1e-12)
            like = self._sigmoid(beta * margin)
            # Avoid zeroing out particles completely.
            self.weights[k] *= 0.15 + 0.85 * like

        self._renormalize()

    def _opp_threshold_frac(self, p: float) -> float:
        # Opponent acceptance threshold (fraction of total) prior; decays over time.
        # Calibrated to be firm early but not impossible.
        return 0.68 - 0.38 * p  # 0.68 -> 0.30

    def _update_from_rejection_of_last(self) -> None:
        """
        If we now see a new opponent offer, it means they rejected our last_sent offer.
        Penalize particles under which they would've accepted last_sent.
        """
        if self.last_sent is None or self.total <= 0.0:
            return

        p = self._progress()
        theta = self._opp_threshold_frac(p) * self.total
        kscale = 0.085 * self.total + 1e-9

        gamma = 1.4  # rejection evidence strength

        for idx, u in enumerate(self.particles):
            give_val = 0.0
            for i in range(self.n):
                give_val += self.last_sent[i] * u[i]
            keep_val = self.total - give_val

            p_accept = self._sigmoid((keep_val - theta) / kscale)
            # Rejection likelihood is ~ (1 - p_accept), softened.
            rej_like = max(1e-6, 1.0 - p_accept)
            self.weights[idx] *= rej_like ** gamma

        self._renormalize()

    # ------------------------- accept / concede -------------------------

    def _my_floor(self) -> float:
        if self.total <= 0.0:
            return 0.0

        p = self._progress()

        # Concede over time: high early, moderate late.
        frac = 0.90 - 0.55 * p  # 0.90 -> 0.35

        last_turn = (self.t >= self.max_rounds - 1)

        # If we are second on the last turn, we should accept rather than counter (counter => guaranteed 0).
        if last_turn and self.me == 1:
            frac = 0.0

        # If we are first on our last turn, make sure we can still strike a deal.
        if last_turn and self.me == 0:
            frac = min(frac, 0.22)

        floor = frac * self.total

        # Don't drop too far below best we've seen unless very late.
        floor = max(floor, self.best_seen - (0.10 + 0.18 * p) * self.total)

        # Never accept microscopic deals (unless last turn second -> frac=0 already).
        if not (last_turn and self.me == 1):
            floor = max(floor, 0.12 * self.total)

        if floor < 0.0:
            floor = 0.0
        if floor > self.total:
            floor = self.total
        return floor

    # ----------------------- acceptance probability ---------------------

    def _p_opp_accept(self, offer_to_me: list[int]) -> float:
        if self.total <= 0.0:
            return 1.0

        p = self._progress()
        theta = self._opp_threshold_frac(p) * self.total
        kscale = 0.085 * self.total + 1e-9

        acc = 0.0
        for w, u in zip(self.weights, self.particles):
            give_val = 0.0
            for i in range(self.n):
                give_val += offer_to_me[i] * u[i]
            keep_val = self.total - give_val
            acc += w * self._sigmoid((keep_val - theta) / kscale)
        return acc

    # -------------------------- offer generation ------------------------

    def _base_take(self) -> list[int]:
        # Take all items we value positively; give away all items we value 0.
        o = self.counts[:]
        for i, v in enumerate(self.values):
            if v <= 0:
                o[i] = 0
        return o

    def _greedy_to_target(self, target_my_value: float, opp_unit_mean: list[float]) -> list[int]:
        """
        Start from base (take everything valuable), then concede 1 unit at a time
        from items that are valuable to opponent (mean) per our cost, until <= target.
        """
        o = self._base_take()
        myv = self._my_value(o)

        if myv <= target_my_value or self.total <= 0.0:
            return o

        # Precompute ratios for selecting concession item; updated dynamically but cheap at n<=10.
        for _ in range(10000):  # hard cap for safety
            if myv <= target_my_value:
                break
            best_i = -1
            best_ratio = -1.0
            for i in range(self.n):
                if o[i] <= 0:
                    continue
                mv = self.values[i]
                if mv <= 0:
                    continue
                ratio = opp_unit_mean[i] / (mv + 1e-9)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_i = i
            if best_i < 0:
                break
            o[best_i] -= 1
            myv -= self.values[best_i]

        return o

    def _random_concession(self, opp_unit_mean: list[float]) -> list[int]:
        """
        Randomized offer: start from base take-all, then concede per-type based on:
        - time (more concessions later),
        - opponent/our ratio (concede more when cheap to us, likely valuable to them).
        """
        p = self._progress()
        o = self._base_take()

        for i in range(self.n):
            c = self.counts[i]
            if c <= 0:
                continue
            if self.values[i] <= 0:
                o[i] = 0
                continue

            ratio = opp_unit_mean[i] / (self.values[i] + 1e-9)
            # 0..1, increases with ratio and time
            base = ratio / (1.0 + ratio)
            inten = (0.10 + 0.75 * p) * base

            # Skew random so early tends to concede little, later more.
            r = self.rng.random()
            r = r ** (1.8 - 1.1 * p)  # early: small; late: larger
            give = int((inten * r) * (c + 0.5))

            o[i] = max(0, o[i] - min(o[i], give))

        return o

    def _tweak_take_more(self, their_offer: list[int], k: int = 1) -> list[int]:
        """
        Try a slightly more demanding version of their offer: take +k of our highest value types.
        """
        o = their_offer[:]
        # Sort types by our unit value descending.
        idxs = list(range(self.n))
        idxs.sort(key=lambda i: self.values[i], reverse=True)
        for i in idxs:
            if self.values[i] <= 0:
                continue
            if o[i] < self.counts[i]:
                o[i] = min(self.counts[i], o[i] + k)
                break
        # Still give away our zero-value items (always helps acceptance).
        for i in range(self.n):
            if self.values[i] <= 0:
                o[i] = 0
        return o

    def _choose_counter(self, their_offer: list[int] | None) -> list[int]:
        if self.total <= 0.0:
            return [0] * self.n

        floor = self._my_floor()
        p = self._progress()
        opp_mu = self._mean_opp_unit()

        # Candidate set (deduplicate by tuple).
        cand = {}
        def add(x):
            if not self._valid_offer(x):
                return
            cand[tuple(x)] = x

        # Greedy targets: anchor high early, converge toward floor.
        high = min(self.total, (0.97 - 0.22 * p) * self.total)
        high = max(high, floor)

        steps = [0.00, 0.06, 0.12, 0.18, 0.25, 0.34]
        for s in steps:
            tgt = max(floor, high - s * self.total)
            add(self._greedy_to_target(tgt, opp_mu))

        # Add randomized offers.
        # Slightly fewer later to keep stability; still enough to escape local traps.
        n_rand = 80 if p < 0.65 else 55
        for _ in range(n_rand):
            add(self._random_concession(opp_mu))

        # Include their offer and a couple of slight "take more" tweaks.
        if their_offer is not None:
            add(their_offer)
            add(self._tweak_take_more(their_offer, k=1))
            add(self._tweak_take_more(their_offer, k=2))

        # Score candidates.
        best = None
        best_score = -1e30

        last_turn = (self.t >= self.max_rounds - 1)
        for off in cand.values():
            myv = self._my_value(off)
            if myv + 1e-9 < floor and not (last_turn and self.me == 1):
                continue

            pacc = self._p_opp_accept(off)

            # Late game: favor higher acceptance probability more.
            w_acc = 0.55 + 0.35 * p
            score = myv * ((1.0 - w_acc) + w_acc * pacc)

            # Gentle tie-break: prefer offers that are more likely to close, especially late.
            score += (0.02 + 0.05 * p) * self.total * pacc

            if score > best_score:
                best_score = score
                best = off

        # Fallback (shouldn't happen).
        if best is None:
            best = self._base_take()

        self.last_sent = best[:]
        return best

    # ------------------------------- API -------------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Total value 0: accept anything valid; otherwise propose zeros.
        if self.total_int <= 0:
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        last_turn = (self.t >= self.max_rounds - 1)

        # If we are second and it's our last decision: never counter (counter => guaranteed 0 outcome).
        if last_turn and self.me == 1 and o is not None and self._valid_offer(o):
            return None

        # Process incoming offer.
        if o is not None:
            if not self._valid_offer(o):
                # Safe valid response.
                counter = self._choose_counter(None)
                self.t += 1
                return counter

            myv = self._my_value(o)
            if myv > self.best_seen:
                self.best_seen = myv

            # Seeing their new offer implies they rejected our last sent offer (if any).
            self._update_from_rejection_of_last()
            # Update from their current offer content.
            self._update_from_their_offer(o)

            # Accept if it meets our floor.
            if myv + 1e-9 >= self._my_floor():
                self.t += 1
                return None

            # Extra safety: late-ish, accept good offers that are very likely to settle.
            if self._progress() > 0.70:
                if myv >= 0.45 * self.total and self._p_opp_accept(o) > 0.92:
                    self.t += 1
                    return None
        else:
            # We start; no rejection inference.
            self.last_sent = None

        counter = self._choose_counter(o)
        self.t += 1
        return counter