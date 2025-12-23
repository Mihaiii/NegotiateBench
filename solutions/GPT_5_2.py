import math
import random


class Agent:
    """
    IMPORTANT (matches the provided negotiation transcripts/profits):
    - Incoming offer `o` is how many items THE OPPONENT WANTS TO KEEP for themselves.
    - If we accept, we will receive counts - o.
    - If we counter (return a list), it is how many items WE want to keep for ourselves.
    - Returning None means ACCEPT (only valid when o is not None).

    Strategy:
    - Particle belief over opponent per-unit values u[i] >= 0 with the constraint:
        sum_i counts[i] * u[i] == our_total
    - Update belief from:
        (a) opponent offers (they tend to keep what they value)
        (b) opponent rejecting our last offer (their kept value likely below a time-dependent threshold)
    - Choose counter-offers that meet our time-dependent value floor while minimizing opponent "loss"
      (value of items we keep), using DP when feasible.
    """

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_int = sum(c * v for c, v in zip(self.counts, self.values))
        self.total = float(self.total_int)

        # our turn index among our own turns: 0..max_rounds-1
        self.step = 0

        # last offer we sent: how many we want to KEEP
        self.last_sent_keep = None

        # best sure value we've seen (by accepting some opponent offer)
        self.best_seen = 0

        seed = (
            1000003 * sum(self.counts)
            + 9176 * sum(self.values)
            + 131 * self.max_rounds
            + 7 * self.me
        ) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        self.pos_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        self.zero_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] <= 0]

        self.particles, self.weights = self._init_particles(m=240)

    # ------------------------- basic helpers -------------------------

    def _valid_offer_keep(self, o) -> bool:
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

    def _overall_progress(self) -> float:
        """
        Overall turn index in [0, 2*max_rounds-1].
        Our own step is 0..max_rounds-1, and me is 0 (first) or 1 (second).
        """
        if self.max_rounds <= 1:
            return 1.0
        overall = 2 * self.step + self.me
        denom = 2 * self.max_rounds - 1
        p = overall / denom
        return 0.0 if p < 0.0 else (1.0 if p > 1.0 else p)

    def _is_last_our_turn(self) -> bool:
        return self.step >= self.max_rounds - 1

    def _my_value_keep(self, my_keep: list[int]) -> int:
        return sum(self.values[i] * my_keep[i] for i in range(self.n))

    def _my_keep_from_their_keep(self, their_keep: list[int]) -> list[int]:
        return [self.counts[i] - their_keep[i] for i in range(self.n)]

    def _their_keep_from_my_keep(self, my_keep: list[int]) -> list[int]:
        return [self.counts[i] - my_keep[i] for i in range(self.n)]

    # ------------------------- opponent belief -------------------------

    def _scaled_from_weights(self, w: list[float]) -> list[float]:
        denom = sum(self.counts[i] * w[i] for i in range(self.n))
        if denom <= 1e-12 or self.total <= 0.0:
            return [0.0] * self.n
        s = self.total / denom
        return [max(0.0, wi * s) for wi in w]

    def _init_particles(self, m: int = 240):
        if self.total_int <= 0:
            return [[0.0] * self.n], [1.0]

        parts = []
        eps = 1e-6

        # Extremes: concentrate on one type
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            parts.append(self._scaled_from_weights(w))

        # Uniform
        parts.append(self._scaled_from_weights([1.0] * self.n))

        # Correlated with our values (often, but not always)
        parts.append(self._scaled_from_weights([max(eps, float(v)) for v in self.values]))

        # Random exponential weights (Dirichlet-ish)
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

    def _opp_value_keep(self, their_keep: list[int], u: list[float]) -> float:
        return sum(their_keep[i] * u[i] for i in range(self.n))

    def _theta_accept(self) -> float:
        # Opponent acceptance threshold (their value of what they KEEP), decreasing with time.
        p = self._overall_progress()
        frac = 0.72 - 0.50 * (p ** 1.15)  # ~0.72 -> ~0.22
        if frac < 0.18:
            frac = 0.18
        return frac * self.total

    def _theta_offer(self) -> float:
        # Opponent offers often target a bit above what they'd accept.
        p = self._overall_progress()
        frac = 0.80 - 0.42 * (p ** 1.10)  # ~0.80 -> ~0.38
        if frac < 0.28:
            frac = 0.28
        if frac > 0.88:
            frac = 0.88
        return frac * self.total

    def _update_from_rejection_of_last(self) -> None:
        if self.last_sent_keep is None or self.total_int <= 0:
            return
        theta = self._theta_accept()
        kscale = 0.10 * self.total + 1e-9

        their_keep = self._their_keep_from_my_keep(self.last_sent_keep)
        for k, u in enumerate(self.particles):
            v_keep = self._opp_value_keep(their_keep, u)
            p_acc = self._sigmoid((v_keep - theta) / kscale)
            # They rejected, so particles where acceptance was likely are downweighted.
            self.weights[k] *= max(1e-6, (1.0 - p_acc)) ** 1.15
        self._renormalize()

    def _update_from_their_offer(self, their_keep: list[int]) -> None:
        if self.total_int <= 0:
            return
        theta = self._theta_offer()
        kscale = 0.12 * self.total + 1e-9

        for k, u in enumerate(self.particles):
            keep_v = self._opp_value_keep(their_keep, u)
            like = 0.05 + 0.95 * self._sigmoid((keep_v - theta) / kscale)
            self.weights[k] *= like
        self._renormalize()

    def _p_opp_accept_my_keep(self, my_keep: list[int]) -> float:
        if self.total_int <= 0:
            return 1.0
        theta = self._theta_accept()
        kscale = 0.10 * self.total + 1e-9
        their_keep = self._their_keep_from_my_keep(my_keep)

        acc = 0.0
        for w, u in zip(self.weights, self.particles):
            v_keep = self._opp_value_keep(their_keep, u)
            acc += w * self._sigmoid((v_keep - theta) / kscale)
        return acc

    # ------------------------- my thresholds -------------------------

    def _my_floor(self) -> float:
        if self.total_int <= 0:
            return 0.0

        p = self._overall_progress()
        last = self._is_last_our_turn()

        # If we are second and it's our last turn, countering yields 0 for sure -> accept anything (>=0).
        if last and self.me == 1:
            return 0.0

        # Concede over time.
        frac = 0.92 - 0.66 * (p ** 1.20)  # ~0.92 -> ~0.26
        if frac < 0.16:
            frac = 0.16

        # If we're first and it's our last turn to propose, we need to close.
        if last and self.me == 0:
            frac = min(frac, 0.22)

        floor = frac * self.total

        # Don't drop far below the best sure offer we've seen, unless late.
        floor = max(floor, self.best_seen - (0.06 + 0.33 * p) * self.total)

        if floor < 0.0:
            return 0.0
        if floor > self.total:
            return self.total
        return floor

    # ------------------------- offer construction -------------------------

    def _base_ask_keep(self) -> list[int]:
        # We keep all items that have positive value to us; give all zero-value items away.
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _dp_min_opp_loss_for_my_value(self, opp_mu: list[float]):
        """
        DP over achievable my_value.
        dp[v] = minimal opponent-loss (expected opponent value of items we keep) to achieve exact v.
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
                for x in range(c + 1):  # x units we keep
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

    def _reconstruct_keep(self, types, prevs, takes, v_target: int) -> list[int]:
        my_keep = [0] * self.n
        v = v_target
        for stage in range(len(types) - 1, -1, -1):
            idx = types[stage]
            x = takes[stage][v]
            my_keep[idx] = x
            v = prevs[stage][v] if v >= 0 else 0
        # always give away zero-valued types
        for i in self.zero_types:
            my_keep[i] = 0
        return my_keep

    def _greedy_for_target_keep(self, opp_mu: list[float], target_value: int) -> list[int]:
        # Start from keeping everything valuable, then give away units that are "expensive" to opponent per our value.
        keep = self._base_ask_keep()
        cur = self._my_value_keep(keep)

        idxs = [i for i in self.pos_types if keep[i] > 0]
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

        for i in self.zero_types:
            keep[i] = 0
        return keep

    def _choose_counter_keep(self, their_keep: list[int] | None) -> list[int]:
        if self.total_int <= 0:
            return [0] * self.n

        p = self._overall_progress()
        floor = self._my_floor()
        floor_i = int(math.ceil(floor - 1e-9))

        opp_mu = self._mean_opp_unit()

        # Candidate target values for us
        fracs = [
            0.99, 0.97, 0.95, 0.92, 0.88, 0.84, 0.80, 0.76, 0.72,
            0.68, 0.64, 0.60, 0.56, 0.52, 0.48, 0.44, 0.40, 0.36,
            0.32, 0.28, 0.24, 0.20
        ]
        targets = {self.total_int, max(0, min(self.total_int, floor_i))}
        for f in fracs:
            targets.add(int(self.total_int * f))

        # Also consider the value we'd get if we accepted their current proposal
        if their_keep is not None:
            my_keep_if_accept = self._my_keep_from_their_keep(their_keep)
            v_acc = self._my_value_keep(my_keep_if_accept)
            targets.add(v_acc)
            targets.add(min(self.total_int, v_acc + int(0.04 * self.total)))

        cand = {}

        def add(x: list[int]):
            for i in self.zero_types:
                x[i] = 0
            if self._valid_offer_keep(x):
                cand[tuple(x)] = x

        add(self._base_ask_keep())

        use_dp = (self.total_int <= 8000 and len(self.pos_types) <= 10)
        if use_dp:
            types, dp_loss, prevs, takes = self._dp_min_opp_loss_for_my_value(opp_mu)
            reachable = [v < 1e80 for v in dp_loss]

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
                        if v == t:
                            break
                if best_v is not None:
                    add(self._reconstruct_keep(types, prevs, takes, best_v))
        else:
            for t in sorted(targets, reverse=True):
                if t < floor_i:
                    continue
                add(self._greedy_for_target_keep(opp_mu, t))

        # Score candidates
        best = None
        best_score = -1e100
        for off in cand.values():
            myv = self._my_value_keep(off)
            if myv + 1e-9 < floor:
                continue

            pacc = self._p_opp_accept_my_keep(off)

            # closeness to their last proposal (helps agreement)
            closeness = 0.0
            if their_keep is not None:
                implied_their_keep = self._their_keep_from_my_keep(off)
                l1 = sum(abs(implied_their_keep[i] - their_keep[i]) for i in range(self.n))
                closeness = -0.012 * self.total * (l1 / max(1, sum(self.counts)))

            # Risk-aware expected utility; later we weight acceptance more.
            accept_weight = 0.35 + 0.55 * p
            score = myv * ((1.0 - accept_weight) + accept_weight * pacc)
            score += (0.02 + 0.10 * p) * self.total * pacc
            score += closeness

            # Avoid hopeless anchors early
            if p < 0.35 and pacc < 0.03:
                score *= 0.35

            if score > best_score:
                best_score = score
                best = off

        if best is None:
            best = self._base_ask_keep()

        self.last_sent_keep = list(best)
        return best

    # ------------------------- main API -------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # If everything is worthless to us, accept anything.
        if self.total_int <= 0:
            self.step += 1
            if o is not None and self._valid_offer_keep(o):
                return None
            return [0] * self.n

        last = self._is_last_our_turn()

        if o is not None:
            if not self._valid_offer_keep(o):
                counter = self._choose_counter_keep(None)
                self.step += 1
                return counter

            their_keep = list(o)
            my_keep_if_accept = self._my_keep_from_their_keep(their_keep)

            # New opponent offer implies our last offer was rejected (if any)
            self._update_from_rejection_of_last()
            self._update_from_their_offer(their_keep)

            myv_accept = self._my_value_keep(my_keep_if_accept)
            if myv_accept > self.best_seen:
                self.best_seen = myv_accept

            # If we're second and it's our last turn: countering forces 0, so accept.
            if last and self.me == 1:
                self.step += 1
                return None

            floor = self._my_floor()

            counter = self._choose_counter_keep(their_keep)
            pacc_counter = self._p_opp_accept_my_keep(counter)
            exp_counter = self._my_value_keep(counter) * pacc_counter

            # Accept if offer meets our floor.
            if myv_accept + 1e-9 >= floor:
                self.step += 1
                return None

            # Late deadlock avoidance: take a modest deal rather than risk 0.
            if self._overall_progress() > 0.88 and myv_accept >= 0.18 * self.total:
                self.step += 1
                return None

            # Compare sure acceptance vs risky counter.
            if myv_accept >= exp_counter - 0.03 * self.total:
                self.step += 1
                return None

            self.step += 1
            return counter

        # We start (no incoming offer): send an anchored but acceptance-aware proposal.
        self.last_sent_keep = None
        counter = self._choose_counter_keep(None)
        self.step += 1
        return counter