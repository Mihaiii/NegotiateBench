import math
import random


class Agent:
    """
    Haggling agent for the (common in practice) convention:
      an offer/list denotes what the SPEAKER keeps for themselves.

    Thus, when opponent sends o (their keep), our received share is counts - o.
    When we send an offer, we return what WE want to keep.

    Strategy:
    - Particle belief over opponent per-unit values (nonnegative, scaled so total equals ours).
    - Update belief from opponent offers and rejection of our last offer.
    - Choose counteroffers via bounded-knapsack DP:
        for each achievable my_value, minimize opponent-loss (value of items we keep) under mean opp values,
        which maximizes opponent value for the same my_value -> higher acceptance probability.
    - Time-based concession: high early floor, lower near deadline; forced accept on our final turn if we are second.
    """

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_int = sum(c * v for c, v in zip(self.counts, self.values))
        self.total = float(self.total_int)

        self.step = 0  # how many times offer() was called on us
        self.last_sent = None  # what we last asked to keep
        self.best_seen = 0

        seed = (
            1000003 * sum(self.counts)
            + 9176 * sum(self.values)
            + 131 * self.max_rounds
            + 7 * self.me
        ) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        self.particles, self.weights = self._init_particles(m=180)

    # ----------------------------- basics -----------------------------

    def _valid_offer(self, o) -> bool:
        if not isinstance(o, (list, tuple)) or len(o) != self.n:
            return False
        for i, x in enumerate(o):
            if not isinstance(x, int):
                return False
            if x < 0 or x > self.counts[i]:
                return False
        return True

    def _my_value_keep(self, my_keep: list[int]) -> int:
        return sum(v * x for v, x in zip(self.values, my_keep))

    def _my_value_if_accept(self, opp_keep: list[int]) -> int:
        # We get counts - opp_keep
        return self.total_int - sum(v * x for v, x in zip(self.values, opp_keep))

    def _opp_keep_from_my_keep(self, my_keep: list[int]) -> list[int]:
        return [self.counts[i] - my_keep[i] for i in range(self.n)]

    def _progress(self) -> float:
        # overall turn index in [0, 2*max_rounds-1]
        if self.max_rounds <= 1:
            return 1.0
        overall = 2 * self.step + self.me
        denom = 2 * self.max_rounds - 1
        g = overall / denom
        if g < 0.0:
            return 0.0
        if g > 1.0:
            return 1.0
        return g

    def _is_last_our_turn(self) -> bool:
        return self.step >= self.max_rounds - 1

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z <= -35.0:
            return 0.0
        if z >= 35.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    # -------------------------- opponent belief --------------------------

    def _scaled_from_weights(self, w: list[float]) -> list[float]:
        denom = 0.0
        for i in range(self.n):
            denom += self.counts[i] * w[i]
        if denom <= 1e-12 or self.total <= 0.0:
            return [0.0] * self.n
        s = self.total / denom
        return [max(0.0, wi * s) for wi in w]

    def _init_particles(self, m: int = 180):
        if self.total_int <= 0:
            return [[0.0] * self.n], [1.0]

        parts = []
        eps = 1e-6

        # Extremes
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            parts.append(self._scaled_from_weights(w))

        # Uniform
        parts.append(self._scaled_from_weights([1.0] * self.n))

        # Random smooth
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
        if not (s > 0.0) or math.isinf(s) or math.isnan(s):
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

    def _opp_value_keep(self, keep: list[int], u: list[float]) -> float:
        return sum(keep[i] * u[i] for i in range(self.n))

    def _theta_accept(self) -> float:
        # Opponent acceptance threshold (value they keep), decreases with time.
        p = self._progress()
        frac = 0.68 - 0.40 * (p ** 1.10)  # ~0.68 -> ~0.28
        if frac < 0.22:
            frac = 0.22
        return frac * self.total

    def _theta_offer(self) -> float:
        # When they make an offer, they tend to ask a bit more than they'd accept.
        p = self._progress()
        frac = 0.75 - 0.34 * (p ** 1.05)  # ~0.75 -> ~0.41
        if frac < 0.30:
            frac = 0.30
        if frac > 0.80:
            frac = 0.80
        return frac * self.total

    def _update_from_rejection_of_last(self) -> None:
        if self.last_sent is None or self.total_int <= 0:
            return
        theta = self._theta_accept()
        kscale = 0.085 * self.total + 1e-9

        # They rejected, so under a particle where they'd likely accept, downweight it.
        opp_keep = self._opp_keep_from_my_keep(self.last_sent)
        for k, u in enumerate(self.particles):
            v = self._opp_value_keep(opp_keep, u)
            p_acc = self._sigmoid((v - theta) / kscale)
            self.weights[k] *= max(1e-6, (1.0 - p_acc)) ** 1.20
        self._renormalize()

    def _update_from_their_offer(self, opp_keep: list[int]) -> None:
        if self.total_int <= 0:
            return
        theta = self._theta_offer()
        kscale = 0.10 * self.total + 1e-9

        for k, u in enumerate(self.particles):
            keep_v = self._opp_value_keep(opp_keep, u)
            like = 0.08 + 0.92 * self._sigmoid((keep_v - theta) / kscale)
            self.weights[k] *= like
        self._renormalize()

    def _p_opp_accept(self, my_keep: list[int]) -> float:
        if self.total_int <= 0:
            return 1.0
        theta = self._theta_accept()
        kscale = 0.085 * self.total + 1e-9
        opp_keep = self._opp_keep_from_my_keep(my_keep)

        acc = 0.0
        for w, u in zip(self.weights, self.particles):
            v = self._opp_value_keep(opp_keep, u)
            acc += w * self._sigmoid((v - theta) / kscale)
        return acc

    # -------------------------- my thresholds --------------------------

    def _my_floor(self) -> float:
        if self.total_int <= 0:
            return 0.0

        p = self._progress()
        last = self._is_last_our_turn()

        # If we're second and it's our last turn, we must accept (countering ends negotiations with 0).
        if last and self.me == 1:
            return 0.0

        # Start tough, concede.
        frac = 0.93 - 0.55 * (p ** 1.20)  # ~0.93 -> ~0.38
        if frac < 0.18:
            frac = 0.18

        # If we are first and it's our last turn, we can offer something very reasonable to close.
        if last and self.me == 0:
            frac = min(frac, 0.20)

        floor = frac * self.total

        # Don't accept tiny deals unless near end.
        floor = max(floor, (0.10 if p > 0.85 else 0.16) * self.total)

        # Also don't accept far below best seen, unless late.
        floor = max(floor, self.best_seen - (0.10 + 0.28 * p) * self.total)

        if floor < 0.0:
            return 0.0
        if floor > self.total:
            return self.total
        return floor

    # -------------------------- offer construction --------------------------

    def _base_take(self) -> list[int]:
        # Keep all items with positive value to us; give away our zero-value items.
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _tweak_ask_more(self, my_keep: list[int], k: int = 1) -> list[int]:
        o = list(my_keep)
        # Never keep zero-value items
        for i in range(self.n):
            if self.values[i] <= 0:
                o[i] = 0
        # add k units from the most valuable type where possible
        idxs = list(range(self.n))
        idxs.sort(key=lambda i: self.values[i], reverse=True)
        for i in idxs:
            if self.values[i] > 0 and o[i] < self.counts[i]:
                o[i] = min(self.counts[i], o[i] + k)
                break
        return o

    def _dp_best_for_opp_given_my_value(self, opp_mu: list[float]):
        """
        DP over types with values[i] > 0:
          dp[v] = minimal opp_loss = sum(my_keep_i * opp_mu[i]) to achieve my_value == v.
        Returns (types, dp, prevs, takes).
        """
        V = self.total_int
        INF = 1e100

        types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        if not types or V <= 0:
            return types, [0.0] + [INF] * V, [], []

        dp = [INF] * (V + 1)
        dp[0] = 0.0
        prevs, takes = [], []

        for idx in types:
            c = self.counts[idx]
            mv = self.values[idx]
            ov = float(opp_mu[idx])

            new = [INF] * (V + 1)
            prev = [-1] * (V + 1)
            take = [0] * (V + 1)

            for v0 in range(V + 1):
                base = dp[v0]
                if base >= INF:
                    continue
                for x in range(c + 1):
                    v = v0 + x * mv
                    if v > V:
                        break
                    loss = base + x * ov
                    if loss + 1e-12 < new[v]:
                        new[v] = loss
                        prev[v] = v0
                        take[v] = x

            dp = new
            prevs.append(prev)
            takes.append(take)

        return types, dp, prevs, takes

    def _reconstruct_offer(self, types, prevs, takes, v_target: int) -> list[int]:
        my_keep = [0] * self.n
        v = v_target
        for stage in range(len(types) - 1, -1, -1):
            idx = types[stage]
            x = takes[stage][v]
            my_keep[idx] = x
            v = prevs[stage][v] if v >= 0 else 0

        for i in range(self.n):
            if self.values[i] <= 0:
                my_keep[i] = 0
        return my_keep

    def _greedy_offer_for_target(self, opp_mu: list[float], target_value: int) -> list[int]:
        """
        If DP would be too large, start from base_take and give away units that are
        "expensive for opponent per value we gain" (high opp_mu/value) while staying >= target_value.
        """
        keep = self._base_take()
        cur = self._my_value_keep(keep)

        idxs = [i for i in range(self.n) if self.values[i] > 0 and keep[i] > 0]
        idxs.sort(key=lambda i: (opp_mu[i] / max(1e-9, self.values[i])), reverse=True)

        changed = True
        while changed:
            changed = False
            for i in idxs:
                if keep[i] <= 0:
                    continue
                if cur - self.values[i] >= target_value:
                    keep[i] -= 1
                    cur -= self.values[i]
                    changed = True
        return keep

    def _choose_counter(self, opp_keep: list[int] | None) -> list[int]:
        if self.total_int <= 0:
            return [0] * self.n

        p = self._progress()
        floor = self._my_floor()
        floor_i = int(math.ceil(floor - 1e-9))
        opp_mu = self._mean_opp_unit()

        # Candidate targets (descending).
        fracs = [0.99, 0.97, 0.95, 0.92, 0.88, 0.84, 0.80, 0.76, 0.72, 0.68,
                 0.64, 0.60, 0.56, 0.52, 0.48, 0.44, 0.40, 0.36, 0.32, 0.28, 0.24, 0.20]
        targets = {self.total_int, max(0, min(self.total_int, floor_i))}
        for f in fracs:
            targets.add(int(self.total_int * f))

        their_implied_my_keep = None
        if opp_keep is not None:
            their_implied_my_keep = [self.counts[i] - opp_keep[i] for i in range(self.n)]
            targets.add(self._my_value_keep(their_implied_my_keep))
            targets.add(max(0, self._my_value_keep(their_implied_my_keep) + int(0.04 * self.total)))

        # Build candidates.
        cand = {}

        def add(x: list[int]):
            if self._valid_offer(x):
                # never keep our zero-value items
                for i in range(self.n):
                    if self.values[i] <= 0:
                        x[i] = 0
                cand[tuple(x)] = x

        base = self._base_take()
        add(list(base))

        if their_implied_my_keep is not None:
            add(list(their_implied_my_keep))
            add(self._tweak_ask_more(their_implied_my_keep, 1))
            if p < 0.70:
                add(self._tweak_ask_more(their_implied_my_keep, 2))

        # DP / greedy generate Pareto-friendly offers for each target.
        use_dp = self.total_int <= 2500
        if use_dp:
            types, dp_loss, prevs, takes = self._dp_best_for_opp_given_my_value(opp_mu)
            reachable = [x < 1e80 for x in dp_loss]

            def best_reachable_at_or_below(v: int) -> int | None:
                if v > self.total_int:
                    v = self.total_int
                for vv in range(v, -1, -1):
                    if reachable[vv]:
                        return vv
                return None

            for tval in sorted(targets, reverse=True):
                if tval < floor_i:
                    continue
                vv = best_reachable_at_or_below(tval)
                if vv is None or vv < floor_i:
                    continue
                add(self._reconstruct_offer(types, prevs, takes, vv))
        else:
            for tval in sorted(targets, reverse=True):
                if tval < floor_i:
                    continue
                add(self._greedy_offer_for_target(opp_mu, tval))

        # Score: maximize my_value * P(accept), with mild late-game bias to close.
        best = None
        best_score = -1.0
        for off in cand.values():
            myv = self._my_value_keep(off)
            if myv + 1e-9 < floor:
                continue
            pacc = self._p_opp_accept(off)

            score = myv * pacc
            score += (0.015 + 0.07 * p) * self.total * pacc  # closing bias
            score += 1e-6 * myv  # stable tie-break

            # Avoid offers that are almost surely rejected early.
            if p < 0.50 and pacc < 0.03:
                score *= 0.25

            if score > best_score:
                best_score = score
                best = off

        if best is None:
            best = base

        self.last_sent = list(best)
        return best

    # ----------------------------- API -----------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # If all worthless to us, accept any valid offer; otherwise ask to keep nothing (harmless).
        if self.total_int <= 0:
            if o is not None and self._valid_offer(o):
                self.step += 1
                return None
            self.step += 1
            return [0] * self.n

        last = self._is_last_our_turn()

        if o is not None:
            if not self._valid_offer(o):
                counter = self._choose_counter(None)
                self.step += 1
                return counter

            opp_keep = list(o)

            # They made a new offer => they rejected our last one (if any).
            self._update_from_rejection_of_last()
            self._update_from_their_offer(opp_keep)

            myv_accept = self._my_value_if_accept(opp_keep)
            self.best_seen = max(self.best_seen, myv_accept)
            floor = self._my_floor()

            # If we're second and it's our last turn: accept (counter ends with 0 anyway).
            if last and self.me == 1:
                self.step += 1
                return None

            if myv_accept + 1e-9 >= floor:
                self.step += 1
                return None

            # Late game: accept decent deals to avoid deadlock.
            if self._progress() > 0.85 and myv_accept >= 0.33 * self.total:
                self.step += 1
                return None

            counter = self._choose_counter(opp_keep)
            self.step += 1
            return counter

        # We start (no incoming offer).
        self.last_sent = None
        counter = self._choose_counter(None)
        self.step += 1
        return counter