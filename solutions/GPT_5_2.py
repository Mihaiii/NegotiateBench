import math
import random


class Agent:
    """
    Offer semantics (per prompt):
    - Incoming offer `o`: how many items the opponent offers to US (our share).
    - Return None to ACCEPT `o` (only valid if o is not None).
    - Return a list to COUNTER: how many items WE want for ourselves (our share).
    """

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_int = sum(c * v for c, v in zip(self.counts, self.values))
        self.total = float(self.total_int)

        self.step = 0  # our turn index: 0..max_rounds-1
        self.last_sent = None  # last offer we sent (our share)
        self.best_seen = 0  # best value we could have gotten by accepting an observed offer
        self.last_demand_value = None  # monotone concession guard

        seed = (
            1000003 * sum(self.counts)
            + 9176 * sum(self.values)
            + 131 * self.max_rounds
            + 7 * self.me
        ) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        self.pos_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        self.zero_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] == 0]

        # Precompute reachability for sampling integer opponent valuations u with:
        # sum_i counts[i] * u[i] == total_int, u[i] >= 0 integer
        self._reach = self._build_reachability(self.counts, self.total_int, cap=60000)

        self.particles, self.weights = self._init_particles(m=260)

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

    def _my_value(self, my_share: list[int]) -> int:
        return sum(self.values[i] * my_share[i] for i in range(self.n))

    def _their_share_from_my(self, my_share: list[int]) -> list[int]:
        return [self.counts[i] - my_share[i] for i in range(self.n)]

    def _overall_progress(self) -> float:
        # Overall turn index in [0, 2*max_rounds-1]
        if self.max_rounds <= 1:
            return 1.0
        overall = 2 * self.step + self.me
        denom = 2 * self.max_rounds - 1
        p = overall / denom
        if p < 0.0:
            return 0.0
        if p > 1.0:
            return 1.0
        return p

    def _is_last_our_turn(self) -> bool:
        return self.step >= self.max_rounds - 1

    # ------------------------- opponent valuation particles -------------------------

    def _build_reachability(self, coins: list[int], total: int, cap: int = 60000):
        """
        Reachability DP for unbounded coin change: can we form sum s using {coins}?
        Used only for sampling integer opponent per-unit values u with exact total:
            sum coins[i] * u[i] == total
        """
        if total <= 0 or total > cap:
            return None
        coins = [c for c in coins if c > 0]
        if not coins:
            return None
        reach = [False] * (total + 1)
        reach[0] = True
        for s in range(total + 1):
            if not reach[s]:
                continue
            for c in coins:
                ns = s + c
                if ns <= total:
                    reach[ns] = True
        return reach

    def _sample_int_opp_values(self, pref_w: list[float]) -> list[int]:
        """
        Sample u (integer per-unit values) with exact sum_i counts[i]*u[i] == total_int.
        Preference weights pref_w tilt probability of assigning "value steps" to each type.
        """
        if self.total_int <= 0:
            return [0] * self.n

        # Fallback (if reachability too big): scale+adjust integers.
        if self._reach is None:
            eps = 1e-9
            denom = sum(self.counts[i] * max(eps, pref_w[i]) for i in range(self.n))
            if denom <= 0:
                return [0] * self.n
            s = self.total / denom
            u = [max(0, int(round(max(eps, pref_w[i]) * s))) for i in range(self.n)]
            cur = sum(self.counts[i] * u[i] for i in range(self.n))
            # Greedy adjust to hit total exactly (may fail in rare gcd cases; then accept closest).
            idxs = list(range(self.n))
            idxs.sort(key=lambda i: self.counts[i])
            it = 0
            while cur < self.total_int and it < 20000:
                it += 1
                rem = self.total_int - cur
                cand = [i for i in idxs if 0 < self.counts[i] <= rem]
                if not cand:
                    break
                i = max(cand, key=lambda j: pref_w[j])
                u[i] += 1
                cur += self.counts[i]
            it = 0
            while cur > self.total_int and it < 20000:
                it += 1
                rem = cur - self.total_int
                cand = [i for i in idxs if u[i] > 0 and 0 < self.counts[i] <= rem]
                if not cand:
                    break
                i = max(cand, key=lambda j: pref_w[j])
                u[i] -= 1
                cur -= self.counts[i]
            return u

        # Exact sampling via backward walk using reachability.
        u = [0] * self.n
        s = self.total_int
        eps = 1e-12
        for _ in range(1 + self.total_int // max(1, min(c for c in self.counts if c > 0))):
            if s <= 0:
                break
            choices = []
            wsum = 0.0
            for i in range(self.n):
                c = self.counts[i]
                if c <= 0 or s - c < 0:
                    continue
                if not self._reach[s - c]:
                    continue
                w = float(pref_w[i]) + eps
                choices.append((i, c, w))
                wsum += w
            if not choices:
                # Should be extremely rare if reachability is correct; fall back to stop.
                break
            r = self.rng.random() * wsum
            acc = 0.0
            pick_i, pick_c = choices[-1][0], choices[-1][1]
            for i, c, w in choices:
                acc += w
                if acc >= r:
                    pick_i, pick_c = i, c
                    break
            u[pick_i] += 1
            s -= pick_c
        return u

    def _init_particles(self, m: int = 260):
        if self.total_int <= 0:
            return [[0] * self.n], [1.0]

        parts = []
        eps = 1e-6

        # Structured priors: correlated / anti-correlated / uniform / sparse-ish
        base_sets = [
            [1.0] * self.n,
            [max(eps, float(v)) for v in self.values],
            [1.0 / max(1.0, float(v) + 1.0) for v in self.values],
        ]
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            base_sets.append(w)

        for w in base_sets:
            u = self._sample_int_opp_values(w)
            parts.append(u)

        while len(parts) < m:
            # Exponential/Dirichlet-ish preferences
            w = [-math.log(max(1e-12, self.rng.random())) for _ in range(self.n)]
            parts.append(self._sample_int_opp_values(w))

        # Deduplicate particles
        uniq = {}
        for u in parts:
            uniq[tuple(u)] = u
        parts = list(uniq.values())
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

    def _opp_value(self, share: list[int], u: list[int]) -> int:
        return sum(share[i] * u[i] for i in range(self.n))

    # ------------------------- opponent behavior model -------------------------

    def _theta_accept(self) -> float:
        # Threshold for THEIR share to accept, decreases with time.
        p = self._overall_progress()
        frac = 0.86 - 0.66 * (p ** 1.18)  # ~0.86 -> ~0.20
        return max(0.14, min(0.90, frac)) * self.total

    def _theta_offer(self) -> float:
        # When they propose, they tend to aim above their accept threshold.
        p = self._overall_progress()
        frac = 0.92 - 0.58 * (p ** 1.08)  # ~0.92 -> ~0.34
        return max(0.22, min(0.95, frac)) * self.total

    def _my_expected_accept_floor_for_them(self) -> float:
        # What we think THEY believe WE might accept (used as weak signal).
        p = self._overall_progress()
        frac = 0.62 - 0.40 * (p ** 1.15)  # ~0.62 -> ~0.22
        return max(0.18, min(0.70, frac)) * self.total

    def _update_from_rejection_of_last(self) -> None:
        if self.last_sent is None or self.total_int <= 0:
            return
        theta = self._theta_accept()
        kscale = 0.10 * self.total + 1e-9

        their_share = self._their_share_from_my(self.last_sent)
        for k, u in enumerate(self.particles):
            v = float(self._opp_value(their_share, u))
            p_acc = self._sigmoid((v - theta) / kscale)
            # If they rejected, downweight valuations where they would've accepted.
            self.weights[k] *= max(1e-6, (1.0 - p_acc)) ** 1.25
        self._renormalize()

    def _update_from_their_offer(self, my_share: list[int]) -> None:
        if self.total_int <= 0:
            return
        theta = self._theta_offer()
        kscale = 0.12 * self.total + 1e-9

        myv = float(self._my_value(my_share))
        my_like_floor = self._my_expected_accept_floor_for_them()
        mscale = 0.18 * self.total + 1e-9

        their_share = self._their_share_from_my(my_share)
        for k, u in enumerate(self.particles):
            tv = float(self._opp_value(their_share, u))
            like_their = self._sigmoid((tv - theta) / kscale)
            like_us = self._sigmoid((myv - my_like_floor) / mscale)
            like = 0.05 + 0.95 * (0.80 * like_their + 0.20 * like_us)
            self.weights[k] *= like
        self._renormalize()

    def _p_opp_accept(self, my_share: list[int]) -> float:
        if self.total_int <= 0:
            return 1.0
        theta = self._theta_accept()
        kscale = 0.10 * self.total + 1e-9
        their_share = self._their_share_from_my(my_share)

        acc = 0.0
        for w, u in zip(self.weights, self.particles):
            v = float(self._opp_value(their_share, u))
            acc += w * self._sigmoid((v - theta) / kscale)
        return acc

    # ------------------------- my policy -------------------------

    def _my_aspiration(self) -> float:
        if self.total_int <= 0:
            return 0.0

        p = self._overall_progress()
        last = self._is_last_our_turn()

        # If we are second and it's our last turn, countering can't be accepted -> accept anything valid.
        if last and self.me == 1:
            return 0.0

        # Start fairly ambitious, then converge to ensure agreement.
        frac = 0.86 - 0.56 * (p ** 1.12)  # ~0.86 -> ~0.30
        frac = max(0.18, frac)

        # If we are first and it's our last proposal, we must be very closeable.
        if last and self.me == 0:
            frac = min(frac, 0.28)

        floor = frac * self.total

        # Don't go far below best seen unless very late.
        floor = max(floor, self.best_seen - (0.06 + 0.36 * p) * self.total)

        return max(0.0, min(self.total, floor))

    # ------------------------- offer construction -------------------------

    def _base_ask(self) -> list[int]:
        # Keep everything that is worth >0 to us; give away 0-value items.
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _dp_min_opp_taken_for_myvalue(self, opp_mu: list[float]):
        """
        dp[v] = minimal expected opponent value (using opp_mu) of items WE TAKE,
        to achieve exact my value v.
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
                # bounded choice: take x in [0..c]
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

    def _reconstruct(self, types, prevs, takes, v_target: int) -> list[int]:
        my = [0] * self.n
        v = v_target
        for stage in range(len(types) - 1, -1, -1):
            idx = types[stage]
            x = takes[stage][v]
            my[idx] = int(x)
            v = prevs[stage][v] if v >= 0 else 0
        for i in self.zero_types:
            my[i] = 0
        return my

    def _greedy_offer(self, opp_mu: list[float], target_value: int) -> list[int]:
        # Keep all positive-value items, then give away units that help opponent most per our loss.
        keep = self._base_ask()
        cur = self._my_value(keep)

        idxs = [i for i in self.pos_types if keep[i] > 0]
        idxs.sort(key=lambda i: (opp_mu[i] / max(1e-9, self.values[i])), reverse=True)

        while True:
            moved = False
            for i in idxs:
                if keep[i] <= 0:
                    continue
                if cur - self.values[i] >= target_value:
                    keep[i] -= 1
                    cur -= self.values[i]
                    moved = True
            if not moved:
                break

        for i in self.zero_types:
            keep[i] = 0
        return keep

    def _choose_counter(self, their_offer_to_us: list[int] | None):
        if self.total_int <= 0:
            return [0] * self.n, 0.0

        p = self._overall_progress()
        last = self._is_last_our_turn()

        floor = self._my_aspiration()
        floor_i = int(math.ceil(floor - 1e-9))

        opp_mu = self._mean_opp_unit()

        # Candidate targets (in my-value space)
        fracs = [0.98, 0.95, 0.92, 0.88, 0.84, 0.80, 0.76, 0.72, 0.68, 0.64, 0.60, 0.56, 0.52, 0.48, 0.44, 0.40, 0.36, 0.32, 0.28, 0.24, 0.20]
        targets = {self.total_int, max(0, min(self.total_int, floor_i))}
        for f in fracs:
            targets.add(int(self.total_int * f))

        if their_offer_to_us is not None:
            v_acc = self._my_value(their_offer_to_us)
            targets.add(v_acc)
            targets.add(min(self.total_int, v_acc + int(0.04 * self.total)))

        cand = {}

        def add(x: list[int]):
            for i in self.zero_types:
                x[i] = 0
            if self._valid_offer(x):
                cand[tuple(x)] = x

        add(self._base_ask())
        if their_offer_to_us is not None:
            # Include a "nearby" concession from their offer: ask for +1 of our best unit value type if possible.
            near = list(their_offer_to_us)
            best_i = None
            best_v = -1
            for i in self.pos_types:
                if near[i] < self.counts[i] and self.values[i] > best_v:
                    best_v = self.values[i]
                    best_i = i
            if best_i is not None:
                near2 = list(near)
                near2[best_i] += 1
                add(near2)
            add(near)

        # DP if feasible, else greedy.
        dp_ok = (self.total_int <= 18000 and sum(self.counts) <= 80 and len(self.pos_types) <= 10)
        if dp_ok:
            types, dp_loss, prevs, takes = self._dp_min_opp_taken_for_myvalue(opp_mu)
            reachable = [v < 1e80 for v in dp_loss]

            for t in sorted(targets, reverse=True):
                if not last and t < floor_i:
                    continue
                start = max(0, min(self.total_int, t))
                best_v = None
                best_loss = 1e100
                for v in range(start, self.total_int + 1):
                    if reachable[v] and dp_loss[v] + 1e-12 < best_loss:
                        best_loss = dp_loss[v]
                        best_v = v
                        if v == t:
                            break
                if best_v is not None:
                    add(self._reconstruct(types, prevs, takes, best_v))
        else:
            for t in sorted(targets, reverse=True):
                if not last and t < floor_i:
                    continue
                add(self._greedy_offer(opp_mu, t))

        # Score candidates
        best, best_score, best_ev = None, -1e100, 0.0

        # Soft plausibility filter: early don't insist on very low accept-prob offers
        min_pacc = 0.05 + 0.25 * p  # increases with time (we demand plausibility early)

        # Prevent increasing our demand too much after we started conceding
        max_allowed = None
        if self.last_demand_value is not None and p > 0.15:
            max_allowed = self.last_demand_value + int(0.02 * self.total)

        for off in cand.values():
            myv = self._my_value(off)
            if not last and myv + 1e-9 < floor:
                continue
            if max_allowed is not None and myv > max_allowed:
                continue

            pacc = self._p_opp_accept(off)

            if p < 0.45 and pacc < min_pacc:
                continue

            closeness = 0.0
            if their_offer_to_us is not None:
                l1 = sum(abs(off[i] - their_offer_to_us[i]) for i in range(self.n))
                closeness = -(0.010 + 0.035 * p) * self.total * (l1 / max(1, sum(self.counts)))

            # Time-varying emphasis on agreement
            agree_bonus = (0.03 + 0.16 * p) * self.total * pacc

            # Expected immediate value
            ev = myv * pacc

            # Score: early value-heavy; late agreement-heavy
            w = 0.25 + 0.65 * p
            score = (1.0 - w) * myv + w * ev + agree_bonus + closeness

            # Last proposal as first player: prioritize closing
            if last and self.me == 0:
                score = ev + (0.25 * self.total) * pacc + closeness

            if score > best_score:
                best_score, best, best_ev = score, off, ev

        if best is None:
            best = self._base_ask()
            best_ev = self._my_value(best) * self._p_opp_accept(best)

        return list(best), float(best_ev)

    # ------------------------- main API -------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # If everything is worthless to us, accept any valid offer; otherwise offer 0.
        if self.total_int <= 0:
            self.step += 1
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        last = self._is_last_our_turn()

        # Validate incoming offer
        if o is not None and not self._valid_offer(o):
            counter, _ = self._choose_counter(None)
            self.last_sent = counter
            self.last_demand_value = self._my_value(counter)
            self.step += 1
            return counter

        if o is not None:
            # Belief updates
            self._update_from_rejection_of_last()
            self._update_from_their_offer(o)

            myv_accept = self._my_value(o)
            if myv_accept > self.best_seen:
                self.best_seen = myv_accept

            # If we are second and it's our last turn, countering cannot be accepted -> accept.
            if last and self.me == 1:
                self.step += 1
                return None

            floor = self._my_aspiration()

            # Always accept very strong offers (protects from over-modeling)
            if myv_accept >= 0.60 * self.total:
                self.step += 1
                return None

            counter, counter_ev = self._choose_counter(o)

            # Accept if meets aspiration floor
            if myv_accept + 1e-9 >= floor:
                self.step += 1
                return None

            # Very late: avoid zero outcome (nonnegative values)
            p = self._overall_progress()
            if p > 0.92 and myv_accept >= 0.12 * self.total:
                self.step += 1
                return None

            # Compare acceptance vs counter EV with a shrinking margin
            margin = (0.07 - 0.05 * p) * self.total  # early require advantage to reject
            if myv_accept >= counter_ev - margin:
                self.step += 1
                return None

            self.last_sent = counter
            self.last_demand_value = self._my_value(counter)
            self.step += 1
            return counter

        # We start: propose an acceptance-aware anchored deal
        self.last_sent = None
        counter, _ = self._choose_counter(None)
        self.last_sent = counter
        self.last_demand_value = self._my_value(counter)
        self.step += 1
        return counter