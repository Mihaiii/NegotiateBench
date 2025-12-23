import math
import random


class Agent:
    """
    Negotiation agent (deadline haggling) with:
    - Robust inference of incoming-offer convention (either "what we get" or "what speaker keeps").
    - Particle belief over opponent unit-values constrained to match the known total value.
    - Bayesian-ish updates from opponent offers and from their rejection of our last offer.
    - Offer search using a bounded-knapsack DP that, for each achievable my_value, finds the offer
      that is "best for opponent" under estimated opponent values (Pareto-friendly, higher accept rate).
    """

    # ---------------------------- core setup ----------------------------

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_int = sum(c * v for c, v in zip(self.counts, self.values))
        self.total = float(self.total_int)

        self.t = 0  # our action index (0..max_rounds-1)
        self.best_seen = 0
        self.last_sent = None  # our share

        # Incoming offer convention probability:
        # p_as: incoming o already denotes our share
        # p_comp: incoming o denotes speaker's share, so our share is counts - o
        self.p_as = 0.5

        seed = (
            1000003 * sum(self.counts)
            + 9176 * sum(self.values)
            + 131 * self.max_rounds
            + 7 * self.me
        ) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        self.particles, self.weights = self._init_particles(m=170)

    # ----------------------------- utilities ----------------------------

    def _valid_offer(self, o) -> bool:
        if not isinstance(o, (list, tuple)) or len(o) != self.n:
            return False
        for i, x in enumerate(o):
            if not isinstance(x, int):
                return False
            if x < 0 or x > self.counts[i]:
                return False
        return True

    def _my_value(self, my_share: list[int]) -> int:
        return sum(v * x for v, x in zip(self.values, my_share))

    def _opp_share(self, my_share: list[int]) -> list[int]:
        return [self.counts[i] - my_share[i] for i in range(self.n)]

    def _is_last_our_turn(self) -> bool:
        return self.t >= self.max_rounds - 1

    def _progress(self) -> float:
        """Progress in [0,1] across full timeline of turns."""
        if self.max_rounds <= 1:
            return 1.0
        denom = 2 * self.max_rounds - 1
        g = (2 * self.t + self.me) / denom
        if g < 0.0:
            return 0.0
        if g > 1.0:
            return 1.0
        return g

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z <= -35.0:
            return 0.0
        if z >= 35.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    # -------------------------- incoming convention --------------------------

    def _my_share_as_is(self, o_raw: list[int]) -> list[int]:
        return list(o_raw)

    def _my_share_complement(self, o_raw: list[int]) -> list[int]:
        return [self.counts[i] - o_raw[i] for i in range(self.n)]

    def _update_mode_posterior(self, o_raw: list[int]) -> None:
        """Update p_as using how 'selfish/plausible' the raw offer looks for opponent under each mode."""
        if self.total <= 0.0:
            self.p_as = 0.5
            return

        p = self._progress()
        # We assume a typical opponent tries to keep at least ~ (0.62->0.42) of their total value over time.
        keep_frac = 0.62 - 0.20 * p
        theta = keep_frac * self.total
        kscale = 0.10 * self.total + 1e-9
        beta = 1.0  # already in theta/kscale; keep mild

        # For each mode compute evidence = E_particles[ sigmoid((keep - theta)/kscale) ].
        # If mode implies they keep high value, evidence rises.
        # Mode "as_is": opponent keeps counts - o_raw
        # Mode "comp": opponent keeps o_raw
        ev_as = 0.0
        ev_cp = 0.0
        opp_as = self._opp_share(self._my_share_as_is(o_raw))
        opp_cp = self._opp_share(self._my_share_complement(o_raw))

        for w, u in zip(self.weights, self.particles):
            keep_as = 0.0
            keep_cp = 0.0
            for i in range(self.n):
                keep_as += opp_as[i] * u[i]
                keep_cp += opp_cp[i] * u[i]
            ev_as += w * self._sigmoid(beta * (keep_as - theta) / kscale)
            ev_cp += w * self._sigmoid(beta * (keep_cp - theta) / kscale)

        # Bayesian update with mild floor to avoid collapse from noise.
        prior_as = self.p_as
        prior_cp = 1.0 - self.p_as
        like_as = 0.05 + 0.95 * ev_as
        like_cp = 0.05 + 0.95 * ev_cp
        post_as = prior_as * like_as
        post_cp = prior_cp * like_cp
        s = post_as + post_cp
        self.p_as = 0.5 if s <= 1e-18 else (post_as / s)

    def _map_my_share(self, o_raw: list[int]) -> list[int]:
        """MAP interpretation of incoming raw offer."""
        if self.p_as >= 0.5:
            return self._my_share_as_is(o_raw)
        return self._my_share_complement(o_raw)

    # -------------------------- particle belief --------------------------

    def _scaled_from_weights(self, w: list[float]) -> list[float]:
        denom = 0.0
        for i in range(self.n):
            denom += self.counts[i] * w[i]
        if denom <= 1e-12 or self.total <= 0.0:
            return [0.0] * self.n
        s = self.total / denom
        return [max(0.0, wi * s) for wi in w]

    def _init_particles(self, m: int = 170):
        if self.total <= 0.0:
            return [[0.0] * self.n], [1.0]

        parts = []
        eps = 1e-6

        # Extremes: one type dominates.
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            parts.append(self._scaled_from_weights(w))

        # Uniform-ish.
        parts.append(self._scaled_from_weights([1.0] * self.n))

        # Random smooth particles (Exp(1) -> normalized).
        while len(parts) < m:
            w = []
            for _ in range(self.n):
                u = self.rng.random()
                w.append(-math.log(max(1e-12, u)))
            parts.append(self._scaled_from_weights(w))

        wts = [1.0 / len(parts)] * len(parts)
        return parts, wts

    def _renormalize(self) -> None:
        s = 0.0
        for w in self.weights:
            s += w
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

    # -------------------------- belief updates --------------------------

    def _update_from_rejection_of_last(self) -> None:
        if self.last_sent is None or self.total <= 0.0:
            return

        p = self._progress()
        # Opp acceptance threshold drifts down over time.
        theta = (0.74 - 0.45 * p) * self.total
        kscale = 0.09 * self.total + 1e-9

        opp = self._opp_share(self.last_sent)
        for k, u in enumerate(self.particles):
            keep = 0.0
            for i in range(self.n):
                keep += opp[i] * u[i]
            p_acc = self._sigmoid((keep - theta) / kscale)
            # Rejection likelihood ~ (1 - p_acc) with a mild exponent.
            self.weights[k] *= max(1e-6, 1.0 - p_acc) ** 1.25
        self._renormalize()

    def _update_from_their_offer_raw(self, o_raw: list[int]) -> None:
        """Mixture update across the two possible incoming conventions using current p_as."""
        if self.total <= 0.0:
            return

        p = self._progress()
        # Likelihood that opponent would propose such a split if they are somewhat self-interested.
        theta = (0.78 - 0.42 * p) * self.total
        kscale = 0.10 * self.total + 1e-9

        my_as = self._my_share_as_is(o_raw)
        my_cp = self._my_share_complement(o_raw)
        opp_as = self._opp_share(my_as)
        opp_cp = self._opp_share(my_cp)

        p_as = self.p_as
        p_cp = 1.0 - p_as

        for k, u in enumerate(self.particles):
            keep_as = 0.0
            keep_cp = 0.0
            for i in range(self.n):
                keep_as += opp_as[i] * u[i]
                keep_cp += opp_cp[i] * u[i]
            like_as = 0.10 + 0.90 * self._sigmoid((keep_as - theta) / kscale)
            like_cp = 0.10 + 0.90 * self._sigmoid((keep_cp - theta) / kscale)
            self.weights[k] *= (p_as * like_as + p_cp * like_cp)

        self._renormalize()

    # ---------------------- acceptance / thresholds ----------------------

    def _my_floor(self) -> float:
        if self.total <= 0.0:
            return 0.0

        p = self._progress()
        last = self._is_last_our_turn()

        # If we are second on our last turn, we cannot make a counter that can be accepted.
        if last and self.me == 1:
            return 0.0

        # Firm early, concede with time.
        frac = 0.97 - 0.67 * (p ** 1.15)  # ~0.97 -> ~0.30
        if last and self.me == 0:
            frac = min(frac, 0.18)

        floor = frac * self.total

        # Don't accept far below the best we plausibly saw, unless quite late.
        floor = max(floor, self.best_seen - (0.08 + 0.25 * p) * self.total)

        # Avoid tiny deals except in terminal situations.
        floor = max(floor, 0.12 * self.total)

        if floor < 0.0:
            return 0.0
        if floor > self.total:
            return self.total
        return floor

    def _p_opp_accept(self, my_share: list[int]) -> float:
        if self.total <= 0.0:
            return 1.0
        p = self._progress()
        theta = (0.72 - 0.44 * p) * self.total
        kscale = 0.09 * self.total + 1e-9

        opp = self._opp_share(my_share)
        acc = 0.0
        for w, u in zip(self.weights, self.particles):
            keep = 0.0
            for i in range(self.n):
                keep += opp[i] * u[i]
            acc += w * self._sigmoid((keep - theta) / kscale)
        return acc

    # -------------------------- offer generation --------------------------

    def _base_take(self) -> list[int]:
        # Take all items that are positive to us; never take zero-value items (they help opponent accept).
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _dp_best_for_opp_given_my_value(self, opp_mu: list[float]):
        """
        Bounded knapsack DP minimizing 'opp_loss' = sum(x_i * opp_mu[i]) for each achievable my_value,
        where x_i is how many units we take of type i.

        Returns:
          types: indices of types included in DP (values[i] > 0 and count>0)
          dp_loss: list[float] of size V+1, inf if unreachable
          prevs, takes: backpointers per stage to reconstruct an offer for any reachable value.
        """
        V = self.total_int
        INF = 1e100

        types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        if not types or V <= 0:
            dp_loss = [0.0] + [INF] * V
            return types, dp_loss, [], []

        dp = [INF] * (V + 1)
        dp[0] = 0.0

        prevs = []
        takes = []

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
                # try x = 0..c
                # v = v0 + x*mv
                # loss = base + x*ov
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
        my_share = [0] * self.n
        v = v_target
        for stage in range(len(types) - 1, -1, -1):
            idx = types[stage]
            x = takes[stage][v]
            my_share[idx] = x
            v = prevs[stage][v] if v >= 0 else 0

        # Always give away our zero-value items
        for i in range(self.n):
            if self.values[i] <= 0:
                my_share[i] = 0
        return my_share

    def _tweak_ask_more(self, my_share: list[int], k: int = 1) -> list[int]:
        o = list(my_share)
        for i in range(self.n):
            if self.values[i] <= 0:
                o[i] = 0
        # ask +k in our most valuable available type
        idxs = list(range(self.n))
        idxs.sort(key=lambda i: self.values[i], reverse=True)
        for i in idxs:
            if self.values[i] > 0 and o[i] < self.counts[i]:
                o[i] = min(self.counts[i], o[i] + k)
                break
        return o

    def _midpoint_offer(self, a: list[int], b: list[int]) -> list[int]:
        o = [0] * self.n
        for i in range(self.n):
            o[i] = (a[i] + b[i]) // 2
            if self.values[i] <= 0:
                o[i] = 0
        return o

    def _choose_counter(self, their_raw: list[int] | None) -> list[int]:
        if self.total_int <= 0:
            return [0] * self.n

        p = self._progress()
        floor = self._my_floor()
        floor_i = int(math.ceil(floor - 1e-9))
        opp_mu = self._mean_opp_unit()

        # DP efficient offers
        types, dp_loss, prevs, takes = self._dp_best_for_opp_given_my_value(opp_mu)
        reachable = [x < 1e80 for x in dp_loss]

        def best_reachable_at_or_below(v: int) -> int | None:
            if v < 0:
                return None
            if v > self.total_int:
                v = self.total_int
            for vv in range(v, -1, -1):
                if reachable[vv]:
                    return vv
            return None

        # Candidate my_value targets (high -> lower), plus around floor.
        fracs = [0.99, 0.97, 0.95, 0.92, 0.89, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60,
                 0.55, 0.50, 0.46, 0.42, 0.38, 0.34, 0.30, 0.26, 0.22, 0.18]
        targets = {self.total_int, max(0, min(self.total_int, floor_i))}
        for f in fracs:
            targets.add(int(self.total_int * f))

        their_map = None
        if their_raw is not None:
            their_map = self._map_my_share(their_raw)
            targets.add(self._my_value(their_map))
            targets.add(max(0, self._my_value(their_map) - int(0.06 * self.total)))

        # Build candidate offers
        cand = {}

        def add(x: list[int]):
            if self._valid_offer(x):
                cand[tuple(x)] = x

        add(self._base_take())
        if their_map is not None:
            add(their_map)
            add(self._tweak_ask_more(their_map, 1))
            if p < 0.75:
                add(self._tweak_ask_more(their_map, 2))

        # DP-driven offers (Pareto-friendly for opponent at each my_value)
        for tval in sorted(targets, reverse=True):
            if tval < floor_i:
                continue
            vv = best_reachable_at_or_below(tval)
            if vv is None or vv < floor_i:
                continue
            off = self._reconstruct_offer(types, prevs, takes, vv)
            add(off)

        # Include some compromise midpoints near their offer and our base / last.
        base = self._base_take()
        if their_map is not None:
            add(self._midpoint_offer(base, their_map))
        if self.last_sent is not None and their_map is not None:
            add(self._midpoint_offer(self.last_sent, their_map))

        # Score candidates by (approx) expected value of immediate acceptance.
        best = None
        best_score = -1.0

        for off in cand.values():
            myv = self._my_value(off)
            if myv + 1e-9 < floor:
                continue
            pacc = self._p_opp_accept(off)

            # Main objective: myv * p(accept)
            score = myv * pacc

            # Mild late-game closing preference.
            score += (0.02 + 0.06 * p) * self.total * pacc

            # Slight preference for higher myv when pacc ties.
            score += 1e-6 * myv

            if score > best_score:
                best_score = score
                best = off

        if best is None:
            best = self._base_take()

        self.last_sent = list(best)
        return best

    # -------------------------------- API --------------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # If everything is worthless to us: accept any valid offer.
        if self.total_int <= 0:
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        last = self._is_last_our_turn()

        if o is not None:
            if not self._valid_offer(o):
                # Safe valid counter.
                counter = self._choose_counter(None)
                self.t += 1
                return counter

            o_raw = list(o)

            # Rejection signal: opponent made a new offer => rejected our last one (if any).
            self._update_from_rejection_of_last()

            # Update incoming convention belief, then update opponent valuation particles.
            self._update_mode_posterior(o_raw)
            self._update_from_their_offer_raw(o_raw)

            # Evaluate offer under both possible conventions (to avoid catastrophic accept if uncertain).
            my_as = self._my_share_as_is(o_raw)
            my_cp = self._my_share_complement(o_raw)
            v_as = self._my_value(my_as)
            v_cp = self._my_value(my_cp)

            # Track best plausible seen (optimistic).
            self.best_seen = max(self.best_seen, v_as, v_cp)

            floor = self._my_floor()

            # If we are second on final turn, we must accept or end with 0 anyway.
            if last and self.me == 1:
                # Accept if the posterior-expected value is non-trivial (or if any interpretation is good).
                expv = self.p_as * v_as + (1.0 - self.p_as) * v_cp
                if expv >= 0.10 * self.total or max(v_as, v_cp) >= floor:
                    self.t += 1
                    return None
                # Even if low, accepting doesn't hurt vs 0; accept to avoid mistakes.
                self.t += 1
                return None

            # Standard acceptance: accept if (a) both interpretations meet floor, OR
            # (b) the most likely mode meets floor with decent confidence.
            p_as = self.p_as
            if min(v_as, v_cp) + 1e-9 >= floor:
                self.t += 1
                return None
            if p_as >= 0.78 and v_as + 1e-9 >= floor:
                self.t += 1
                return None
            if p_as <= 0.22 and v_cp + 1e-9 >= floor:
                self.t += 1
                return None

            # Late-game: accept solid deals even if slightly below floor.
            if self._progress() > 0.80:
                expv = p_as * v_as + (1.0 - p_as) * v_cp
                if expv >= 0.38 * self.total:
                    self.t += 1
                    return None

            counter = self._choose_counter(o_raw)
            self.t += 1
            return counter

        # We start / no incoming offer.
        self.last_sent = None
        counter = self._choose_counter(None)
        self.t += 1
        return counter