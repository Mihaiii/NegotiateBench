import math
import random


class Agent:
    """
    Correct semantics for this haggling framework:
    - Incoming offer `o` is how many items the opponent proposes to GIVE US (what we get).
    - Our returned offer is how many items WE want to get.
    - Returning None means we ACCEPT the opponent's last offer (o is not None).

    Approach:
    - Maintain a small particle belief over opponent per-unit values u[i] >= 0, scaled so
      sum_i counts[i]*u[i] == our_total (given equal totals).
    - Update belief from opponent offers (they tend to keep what they value) and from their
      rejection of our last offer (they likely rejected if their value would be below a
      time-dependent acceptance threshold).
    - Construct offers that meet a target value for us while minimizing expected opponent
      "loss" (value, under mean u, of items we keep), using DP when feasible or a greedy fallback.
    - Accept if the offer meets our time-dependent floor, or is competitive with our best counter.
    """

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_int = sum(c * v for c, v in zip(self.counts, self.values))
        self.total = float(self.total_int)

        self.step = 0
        self.last_sent = None  # last offer we sent (what we get)
        self.best_seen = 0     # best value we could get by accepting any seen opponent offer

        seed = (
            1000003 * sum(self.counts)
            + 9176 * sum(self.values)
            + 131 * self.max_rounds
            + 7 * self.me
        ) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        self.pos_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        self.zero_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] <= 0]

        self.particles, self.weights = self._init_particles(m=160)

    # ------------------------- basic helpers -------------------------

    def _valid_offer(self, o) -> bool:
        if not isinstance(o, (list, tuple)) or len(o) != self.n:
            return False
        for i, x in enumerate(o):
            if not isinstance(x, int):
                return False
            if x < 0 or x > self.counts[i]:
                return False
        return True

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z <= -35.0:
            return 0.0
        if z >= 35.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    def _progress(self) -> float:
        # overall turn index in [0, 2*max_rounds-1]
        if self.max_rounds <= 1:
            return 1.0
        overall = 2 * self.step + self.me
        denom = 2 * self.max_rounds - 1
        p = overall / denom
        return 0.0 if p < 0.0 else (1.0 if p > 1.0 else p)

    def _is_last_our_turn(self) -> bool:
        return self.step >= self.max_rounds - 1

    def _my_value_get(self, my_get: list[int]) -> int:
        return sum(self.values[i] * my_get[i] for i in range(self.n))

    def _opp_keep_from_my_get(self, my_get: list[int]) -> list[int]:
        # If we get my_get, opponent keeps counts - my_get
        return [self.counts[i] - my_get[i] for i in range(self.n)]

    # ------------------------- opponent belief -------------------------

    def _scaled_from_weights(self, w: list[float]) -> list[float]:
        denom = sum(self.counts[i] * w[i] for i in range(self.n))
        if denom <= 1e-12 or self.total <= 0.0:
            return [0.0] * self.n
        s = self.total / denom
        return [max(0.0, wi * s) for wi in w]

    def _init_particles(self, m: int = 160):
        if self.total_int <= 0:
            return [[0.0] * self.n], [1.0]

        parts = []
        eps = 1e-6

        # Extremes: concentrate value on one type
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            parts.append(self._scaled_from_weights(w))

        # Uniform
        parts.append(self._scaled_from_weights([1.0] * self.n))

        # Correlated with our values (often helpful)
        parts.append(self._scaled_from_weights([max(eps, float(v)) for v in self.values]))

        # Random positive weights
        while len(parts) < m:
            w = [-math.log(max(1e-12, self.rng.random())) for _ in range(self.n)]
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

    def _opp_value_keep(self, opp_keep: list[int], u: list[float]) -> float:
        return sum(opp_keep[i] * u[i] for i in range(self.n))

    def _theta_accept(self) -> float:
        # Estimated opponent acceptance threshold in their own value, decreasing over time.
        p = self._progress()
        frac = 0.72 - 0.48 * (p ** 1.12)  # ~0.72 -> ~0.24
        if frac < 0.20:
            frac = 0.20
        return frac * self.total

    def _theta_offer(self) -> float:
        # Their offers usually ask for somewhat more than their acceptance threshold.
        p = self._progress()
        frac = 0.80 - 0.40 * (p ** 1.08)  # ~0.80 -> ~0.40
        if frac < 0.30:
            frac = 0.30
        if frac > 0.86:
            frac = 0.86
        return frac * self.total

    def _update_from_rejection_of_last(self) -> None:
        if self.last_sent is None or self.total_int <= 0:
            return
        theta = self._theta_accept()
        kscale = 0.09 * self.total + 1e-9

        opp_keep = self._opp_keep_from_my_get(self.last_sent)
        for k, u in enumerate(self.particles):
            v = self._opp_value_keep(opp_keep, u)
            p_acc = self._sigmoid((v - theta) / kscale)
            # If they'd likely accept under this particle but they rejected, downweight it.
            self.weights[k] *= max(1e-6, (1.0 - p_acc)) ** 1.2
        self._renormalize()

    def _update_from_their_offer(self, their_offer_to_us: list[int]) -> None:
        if self.total_int <= 0:
            return
        theta = self._theta_offer()
        kscale = 0.11 * self.total + 1e-9

        opp_keep = self._opp_keep_from_my_get(their_offer_to_us)
        for k, u in enumerate(self.particles):
            keep_v = self._opp_value_keep(opp_keep, u)
            like = 0.06 + 0.94 * self._sigmoid((keep_v - theta) / kscale)
            self.weights[k] *= like
        self._renormalize()

    def _p_opp_accept(self, my_get: list[int]) -> float:
        if self.total_int <= 0:
            return 1.0
        theta = self._theta_accept()
        kscale = 0.09 * self.total + 1e-9
        opp_keep = self._opp_keep_from_my_get(my_get)

        acc = 0.0
        for w, u in zip(self.weights, self.particles):
            v = self._opp_value_keep(opp_keep, u)
            acc += w * self._sigmoid((v - theta) / kscale)
        return acc

    # ------------------------- my thresholds -------------------------

    def _my_floor(self) -> float:
        if self.total_int <= 0:
            return 0.0

        p = self._progress()
        last = self._is_last_our_turn()

        # If we're second and it's our last turn, countering guarantees 0.
        if last and self.me == 1:
            return 0.0

        # Concede over time.
        frac = 0.93 - 0.63 * (p ** 1.25)  # ~0.93 -> ~0.30
        if frac < 0.18:
            frac = 0.18

        # If we're first and it's our last turn, make it easier to close.
        if last and self.me == 0:
            frac = min(frac, 0.22)

        floor = frac * self.total

        # Don't accept far below best seen except late.
        floor = max(floor, self.best_seen - (0.07 + 0.30 * p) * self.total)

        if floor < 0.0:
            return 0.0
        if floor > self.total:
            return self.total
        return floor

    # ------------------------- offer construction -------------------------

    def _base_ask(self) -> list[int]:
        # Ask for all items we value; concede all items we value at 0.
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _dp_min_opp_loss_for_my_value(self, opp_mu: list[float]):
        """
        DP over achievable my_value. dp[v] = minimal expected opponent value of items we keep
        (i.e., "opp_loss") to achieve exactly my_value==v.
        """
        V = self.total_int
        INF = 1e100
        types = list(self.pos_types)
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
                for x in range(c + 1):  # x units of idx we get
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

    def _reconstruct(self, types, prevs, takes, v_target: int) -> list[int]:
        my_get = [0] * self.n
        v = v_target
        for stage in range(len(types) - 1, -1, -1):
            idx = types[stage]
            x = takes[stage][v]
            my_get[idx] = x
            v = prevs[stage][v] if v >= 0 else 0
        for i in self.zero_types:
            my_get[i] = 0
        return my_get

    def _greedy_for_target(self, opp_mu: list[float], target_value: int) -> list[int]:
        # Start from asking for everything valuable, then give away units that matter most to opp per our value.
        get = self._base_ask()
        cur = self._my_value_get(get)

        idxs = [i for i in self.pos_types if get[i] > 0]
        idxs.sort(key=lambda i: (opp_mu[i] / max(1e-9, self.values[i])), reverse=True)

        changed = True
        while changed:
            changed = False
            for i in idxs:
                if get[i] <= 0:
                    continue
                if cur - self.values[i] >= target_value:
                    get[i] -= 1
                    cur -= self.values[i]
                    changed = True

        for i in self.zero_types:
            get[i] = 0
        return get

    def _choose_counter(self, their_offer_to_us: list[int] | None) -> list[int]:
        if self.total_int <= 0:
            return [0] * self.n

        p = self._progress()
        floor = self._my_floor()
        floor_i = int(math.ceil(floor - 1e-9))

        opp_mu = self._mean_opp_unit()

        # Candidate target values for us
        fracs = [0.99, 0.97, 0.95, 0.92, 0.88, 0.84, 0.80, 0.76, 0.72, 0.68,
                 0.64, 0.60, 0.56, 0.52, 0.48, 0.44, 0.40, 0.36, 0.32, 0.28, 0.24, 0.20]
        targets = {self.total_int, max(0, min(self.total_int, floor_i))}
        for f in fracs:
            targets.add(int(self.total_int * f))

        # Also consider their current offer value (and slightly above it)
        if their_offer_to_us is not None:
            v_their = self._my_value_get(their_offer_to_us)
            targets.add(v_their)
            targets.add(min(self.total_int, v_their + int(0.04 * self.total)))

        cand = {}

        def add(x: list[int]):
            for i in self.zero_types:
                x[i] = 0
            if self._valid_offer(x):
                cand[tuple(x)] = x

        add(self._base_ask())

        use_dp = self.total_int <= 5200 and len(self.pos_types) <= 10
        if use_dp:
            types, dp_loss, prevs, takes = self._dp_min_opp_loss_for_my_value(opp_mu)
            reachable = [v < 1e80 for v in dp_loss]

            # For each target, pick the *least opponent-loss* among values >= target.
            for t in sorted(targets, reverse=True):
                if t < floor_i:
                    continue
                best_v = None
                best_loss = 1e100
                start = t if t <= self.total_int else self.total_int
                for v in range(start, self.total_int + 1):
                    if reachable[v] and dp_loss[v] < best_loss - 1e-12:
                        best_loss = dp_loss[v]
                        best_v = v
                        # early exit if we found an exact target with good loss
                        if v == t:
                            break
                if best_v is not None:
                    add(self._reconstruct(types, prevs, takes, best_v))
        else:
            for t in sorted(targets, reverse=True):
                if t < floor_i:
                    continue
                add(self._greedy_for_target(opp_mu, t))

        # Score offers: expected utility with late-stage closing bias
        best = None
        best_score = -1.0
        for off in cand.values():
            myv = self._my_value_get(off)
            if myv + 1e-9 < floor:
                continue
            pacc = self._p_opp_accept(off)

            score = myv * pacc
            score += (0.01 + 0.10 * p) * self.total * pacc  # prefer deals late
            if p < 0.40 and pacc < 0.02:
                score *= 0.25  # avoid hopeless anchors early

            if score > best_score:
                best_score = score
                best = off

        if best is None:
            best = self._base_ask()

        self.last_sent = list(best)
        return best

    # ------------------------- main API -------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # If everything is worthless to us, accept any valid offer; else ask for nothing (doesn't matter).
        if self.total_int <= 0:
            self.step += 1
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        last = self._is_last_our_turn()

        if o is not None:
            if not self._valid_offer(o):
                counter = self._choose_counter(None)
                self.step += 1
                return counter

            their_offer_to_us = list(o)

            # Their new offer implies rejection of our last (if any)
            self._update_from_rejection_of_last()
            self._update_from_their_offer(their_offer_to_us)

            myv_accept = self._my_value_get(their_offer_to_us)
            if myv_accept > self.best_seen:
                self.best_seen = myv_accept

            # If we're second and it's our last turn: countering guarantees 0, so accept.
            if last and self.me == 1:
                self.step += 1
                return None

            floor = self._my_floor()

            counter = self._choose_counter(their_offer_to_us)
            exp_counter = self._my_value_get(counter) * self._p_opp_accept(counter)

            # Accept if it meets our floor, or is competitive with best counter in expectation.
            if myv_accept + 1e-9 >= floor:
                self.step += 1
                return None

            # Late deadlock avoidance: take a modest deal rather than risk 0.
            if self._progress() > 0.86 and myv_accept >= 0.20 * self.total:
                self.step += 1
                return None

            if myv_accept >= exp_counter - 0.02 * self.total:
                self.step += 1
                return None

            self.step += 1
            return counter

        # We start (no incoming offer): send anchored but acceptance-aware proposal.
        self.last_sent = None
        counter = self._choose_counter(None)
        self.step += 1
        return counter