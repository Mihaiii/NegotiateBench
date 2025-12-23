import math
import random


class Agent:
    """
    Practical note (matches many haggling benchmarks, and the user's provided code):
    - An offer/list denotes what the SPEAKER keeps for themselves.
      So if opponent sends `o`, they propose to keep `o` and give us `counts - o`.
      When we return an offer, we return what WE want to keep.
    - Returning None means we accept the opponent's last offer.

    Strategy (rebuilt & fixed):
    - Maintain a light particle belief over opponent per-unit values u[i] >= 0, scaled so
      sum_i counts[i]*u[i] == our_total (known equal totals).
    - Update belief from opponent offers (they tend to keep what they value) and from rejection
      of our last offer (they likely wouldn't accept too-low value for themselves).
    - Construct counteroffers via DP on our value: for each achievable my_value, minimize expected
      opponent loss (value of items we keep) under mean u. This yields Pareto-friendly offers.
    - Acceptance uses a time-based floor + compares against the best counter's expected value.
    """

    # ------------------------- init / helpers -------------------------

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_int = sum(c * v for c, v in zip(self.counts, self.values))
        self.total = float(self.total_int)

        self.step = 0  # number of times offer() has been called on us
        self.last_sent = None  # last offer we sent (what we keep)
        self.best_seen = 0  # best value we could get by accepting any seen opponent offer

        seed = (
            1000003 * sum(self.counts)
            + 9176 * sum(self.values)
            + 131 * self.max_rounds
            + 7 * self.me
        ) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        # Precompute indices
        self.pos_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        self.zero_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] <= 0]

        # Belief
        self.particles, self.weights = self._init_particles(m=140)

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
        # our calls are exactly max_rounds times
        return self.step >= self.max_rounds - 1

    def _my_value_keep(self, my_keep: list[int]) -> int:
        return sum(self.values[i] * my_keep[i] for i in range(self.n))

    def _my_value_if_accept(self, opp_keep: list[int]) -> int:
        # opponent keeps opp_keep, we get counts - opp_keep
        return sum(self.values[i] * (self.counts[i] - opp_keep[i]) for i in range(self.n))

    def _opp_keep_from_my_keep(self, my_keep: list[int]) -> list[int]:
        return [self.counts[i] - my_keep[i] for i in range(self.n)]

    # ------------------------- opponent belief -------------------------

    def _scaled_from_weights(self, w: list[float]) -> list[float]:
        denom = sum(self.counts[i] * w[i] for i in range(self.n))
        if denom <= 1e-12 or self.total <= 0.0:
            return [0.0] * self.n
        s = self.total / denom
        return [max(0.0, wi * s) for wi in w]

    def _init_particles(self, m: int = 140):
        if self.total_int <= 0:
            return [[0.0] * self.n], [1.0]

        parts = []
        eps = 1e-6

        # Extremes: concentrate value on one type
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            parts.append(self._scaled_from_weights(w))

        # Uniform-ish
        parts.append(self._scaled_from_weights([1.0] * self.n))

        # Correlated with our values (often helpful in practice)
        w = [max(eps, float(v)) for v in self.values]
        parts.append(self._scaled_from_weights(w))

        # Random (Exp(1) weights)
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

    def _opp_value_keep(self, keep: list[int], u: list[float]) -> float:
        return sum(keep[i] * u[i] for i in range(self.n))

    def _theta_accept(self) -> float:
        # opponent acceptance threshold in their own value (estimated), decreases with time
        p = self._progress()
        frac = 0.70 - 0.44 * (p ** 1.10)  # ~0.70 -> ~0.26
        if frac < 0.22:
            frac = 0.22
        return frac * self.total

    def _theta_offer(self) -> float:
        # opponent offers typically demand a bit more than their acceptance threshold
        p = self._progress()
        frac = 0.78 - 0.36 * (p ** 1.05)  # ~0.78 -> ~0.42
        frac = 0.30 if frac < 0.30 else (0.85 if frac > 0.85 else frac)
        return frac * self.total

    def _update_from_rejection_of_last(self) -> None:
        if self.last_sent is None or self.total_int <= 0:
            return
        theta = self._theta_accept()
        kscale = 0.09 * self.total + 1e-9

        opp_keep = self._opp_keep_from_my_keep(self.last_sent)
        for k, u in enumerate(self.particles):
            v = self._opp_value_keep(opp_keep, u)
            p_acc = self._sigmoid((v - theta) / kscale)
            # If they'd likely accept under this particle but they rejected, downweight
            self.weights[k] *= max(1e-6, (1.0 - p_acc)) ** 1.25
        self._renormalize()

    def _update_from_their_offer(self, opp_keep: list[int]) -> None:
        if self.total_int <= 0:
            return
        theta = self._theta_offer()
        kscale = 0.11 * self.total + 1e-9

        # Likelihood grows with how good the offer is for them under particle u
        for k, u in enumerate(self.particles):
            keep_v = self._opp_value_keep(opp_keep, u)
            like = 0.07 + 0.93 * self._sigmoid((keep_v - theta) / kscale)
            self.weights[k] *= like
        self._renormalize()

    def _p_opp_accept(self, my_keep: list[int]) -> float:
        if self.total_int <= 0:
            return 1.0
        theta = self._theta_accept()
        kscale = 0.09 * self.total + 1e-9
        opp_keep = self._opp_keep_from_my_keep(my_keep)

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

        # Time concession: tough early, reasonable late.
        frac = 0.92 - 0.62 * (p ** 1.25)  # ~0.92 -> ~0.30
        if frac < 0.18:
            frac = 0.18

        # If we're first and it's our last turn, make a closing-friendly offer.
        if last and self.me == 0:
            frac = min(frac, 0.20)

        floor = frac * self.total

        # Don't accept far below best we've seen unless it's very late.
        floor = max(floor, self.best_seen - (0.08 + 0.30 * p) * self.total)

        if floor < 0.0:
            return 0.0
        if floor > self.total:
            return self.total
        return floor

    # ------------------------- offer construction -------------------------

    def _base_take(self) -> list[int]:
        # Keep all items we value; give away items we don't value
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _dp_best_for_opp_given_my_value(self, opp_mu: list[float]):
        """
        dp[v] = minimal opponent-loss (value of items we keep) to achieve my_value == v.
        We only DP over types where our per-unit value > 0 (since others don't affect my_value).
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
                # choose x units of idx to keep
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

        # Always give away our zero-value items (helps acceptance, never hurts us)
        for i in self.zero_types:
            my_keep[i] = 0
        return my_keep

    def _greedy_offer_for_target(self, opp_mu: list[float], target_value: int) -> list[int]:
        # Start from taking all positive-value items, then give away "opponent-expensive" units until target met.
        keep = self._base_take()
        cur = self._my_value_keep(keep)

        idxs = [i for i in self.pos_types if keep[i] > 0]
        idxs.sort(key=lambda i: (opp_mu[i] / max(1e-9, self.values[i])), reverse=True)

        # give away one unit at a time from the most opponent-valued per our gained value
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

    def _choose_counter(self, opp_keep: list[int] | None) -> list[int]:
        if self.total_int <= 0:
            return [0] * self.n

        p = self._progress()
        floor = self._my_floor()
        floor_i = int(math.ceil(floor - 1e-9))

        opp_mu = self._mean_opp_unit()

        # Candidate target my-values
        fracs = [0.99, 0.97, 0.95, 0.92, 0.88, 0.84, 0.80, 0.76, 0.72, 0.68,
                 0.64, 0.60, 0.56, 0.52, 0.48, 0.44, 0.40, 0.36, 0.32, 0.28, 0.24, 0.20]
        targets = {self.total_int, max(0, min(self.total_int, floor_i))}
        for f in fracs:
            targets.add(int(self.total_int * f))

        # If we saw their offer, also consider matching / slightly improving our ask relative to it
        if opp_keep is not None:
            my_get_if_accept = [self.counts[i] - opp_keep[i] for i in range(self.n)]
            # But remember: our returned offers are what we keep, not what we get
            my_keep_if_match = self._opp_keep_from_my_keep(my_get_if_accept)  # wrong direction, don't use
            # Instead: if they propose opp_keep, then our keep under that offer would be counts - opp_keep
            my_keep_under_their_offer = [self.counts[i] - opp_keep[i] for i in range(self.n)]
            targets.add(self._my_value_keep(my_keep_under_their_offer))
            targets.add(max(0, self._my_value_keep(my_keep_under_their_offer) + int(0.03 * self.total)))

        # Generate offers
        cand = {}

        def add(x: list[int]):
            # fix zero-value items
            for i in self.zero_types:
                x[i] = 0
            if self._valid_offer(x):
                cand[tuple(x)] = x

        add(self._base_take())

        use_dp = self.total_int <= 4200 and len(self.pos_types) <= 10
        if use_dp:
            types, dp_loss, prevs, takes = self._dp_best_for_opp_given_my_value(opp_mu)
            reachable = [x < 1e80 for x in dp_loss]

            def best_reachable_at_or_below(v: int) -> int | None:
                v = self.total_int if v > self.total_int else v
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

        # Score offers: maximize expected utility with closing bias
        best = None
        best_score = -1.0
        for off in cand.values():
            myv = self._my_value_keep(off)
            if myv + 1e-9 < floor:
                continue
            pacc = self._p_opp_accept(off)

            score = myv * pacc
            score += (0.01 + 0.09 * p) * self.total * pacc  # close late
            score += 1e-6 * myv  # tie-break stability

            # avoid "hopeless" offers early
            if p < 0.45 and pacc < 0.02:
                score *= 0.20

            if score > best_score:
                best_score = score
                best = off

        if best is None:
            best = self._base_take()

        self.last_sent = list(best)
        return best

    # ------------------------- main API -------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # If everything is worthless to us, accept any valid offer; else propose giving everything away.
        if self.total_int <= 0:
            self.step += 1
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        last = self._is_last_our_turn()

        # If we received an opponent offer (remember: it's what THEY keep)
        if o is not None:
            if not self._valid_offer(o):
                counter = self._choose_counter(None)
                self.step += 1
                return counter

            opp_keep = list(o)

            # Their new offer implies rejection of our last (if any)
            self._update_from_rejection_of_last()
            self._update_from_their_offer(opp_keep)

            myv_accept = self._my_value_if_accept(opp_keep)
            if myv_accept > self.best_seen:
                self.best_seen = myv_accept

            # If we're second and it's our last turn: accept anything (counter => guaranteed 0).
            if last and self.me == 1:
                self.step += 1
                return None

            floor = self._my_floor()

            # Compute a good counter and compare vs accepting
            counter = self._choose_counter(opp_keep)
            exp_counter = self._my_value_keep(counter) * self._p_opp_accept(counter)

            # Accept if it meets floor, or if it's at least as good as our best counter in expectation
            if myv_accept + 1e-9 >= floor:
                self.step += 1
                return None

            # Late-game deadlock avoidance
            if self._progress() > 0.85 and myv_accept >= 0.22 * self.total:
                self.step += 1
                return None

            if myv_accept >= exp_counter - 0.03 * self.total:
                self.step += 1
                return None

            self.step += 1
            return counter

        # We start (no incoming offer): make an anchored but DP-friendly demand
        self.last_sent = None
        counter = self._choose_counter(None)
        self.step += 1
        return counter