import math
import random


class Agent:
    """
    Framework semantics (IMPORTANT):
    - Incoming offer `o` is how many items the opponent offers to US (our share).
    - If we accept, we return None and receive exactly `o`.
    - If we counter (return a list), it is how many items WE want for ourselves (our share).
    """

    # ------------------------- init -------------------------

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
        self.best_seen = 0  # best sure value we could get by accepting an observed offer

        seed = (
            1000003 * sum(self.counts)
            + 9176 * sum(self.values)
            + 131 * self.max_rounds
            + 7 * self.me
        ) & 0xFFFFFFFF
        self.rng = random.Random(seed)

        self.pos_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        self.zero_types = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] == 0]

        self.particles, self.weights = self._init_particles(m=200)

    # ------------------------- helpers -------------------------

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
        # overall turn index in [0, 2*max_rounds-1]
        if self.max_rounds <= 1:
            return 1.0
        overall = 2 * self.step + self.me
        denom = 2 * self.max_rounds - 1
        p = overall / denom
        return 0.0 if p < 0.0 else (1.0 if p > 1.0 else p)

    def _is_last_our_turn(self) -> bool:
        return self.step >= self.max_rounds - 1

    # ------------------------- opponent belief (particles) -------------------------

    def _scaled_from_weights(self, w: list[float]) -> list[float]:
        denom = sum(self.counts[i] * w[i] for i in range(self.n))
        if denom <= 1e-12 or self.total <= 0.0:
            return [0.0] * self.n
        s = self.total / denom
        return [max(0.0, wi * s) for wi in w]

    def _init_particles(self, m: int = 200):
        if self.total_int <= 0:
            return [[0.0] * self.n], [1.0]

        eps = 1e-6
        parts = []

        # Extremes: all value on one type
        for j in range(self.n):
            w = [eps] * self.n
            w[j] = 1.0
            parts.append(self._scaled_from_weights(w))

        # Uniform and correlated-with-us priors
        parts.append(self._scaled_from_weights([1.0] * self.n))
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

    def _opp_value(self, share: list[int], u: list[float]) -> float:
        return sum(share[i] * u[i] for i in range(self.n))

    def _theta_accept(self) -> float:
        # Opponent acceptance threshold for THEIR share, decreasing with time.
        p = self._overall_progress()
        frac = 0.84 - 0.62 * (p ** 1.25)  # ~0.84 -> ~0.22
        return max(0.18, min(0.90, frac)) * self.total

    def _theta_offer(self) -> float:
        # Opponent's self-target when making offers: a bit above accept threshold.
        p = self._overall_progress()
        frac = 0.90 - 0.55 * (p ** 1.10)  # ~0.90 -> ~0.35
        return max(0.25, min(0.95, frac)) * self.total

    def _update_from_rejection_of_last(self) -> None:
        if self.last_sent is None or self.total_int <= 0:
            return
        theta = self._theta_accept()
        kscale = 0.11 * self.total + 1e-9

        their_share = self._their_share_from_my(self.last_sent)
        for k, u in enumerate(self.particles):
            v = self._opp_value(their_share, u)
            p_acc = self._sigmoid((v - theta) / kscale)
            self.weights[k] *= max(1e-6, (1.0 - p_acc)) ** 1.15
        self._renormalize()

    def _update_from_their_offer(self, my_share: list[int]) -> None:
        if self.total_int <= 0:
            return
        theta = self._theta_offer()
        kscale = 0.13 * self.total + 1e-9

        their_share = self._their_share_from_my(my_share)
        for k, u in enumerate(self.particles):
            v = self._opp_value(their_share, u)
            like = 0.06 + 0.94 * self._sigmoid((v - theta) / kscale)
            self.weights[k] *= like
        self._renormalize()

    def _p_opp_accept(self, my_share: list[int]) -> float:
        if self.total_int <= 0:
            return 1.0
        theta = self._theta_accept()
        kscale = 0.11 * self.total + 1e-9
        their_share = self._their_share_from_my(my_share)

        acc = 0.0
        for w, u in zip(self.weights, self.particles):
            v = self._opp_value(their_share, u)
            acc += w * self._sigmoid((v - theta) / kscale)
        return acc

    # ------------------------- my thresholds -------------------------

    def _my_floor(self) -> float:
        if self.total_int <= 0:
            return 0.0

        p = self._overall_progress()
        last = self._is_last_our_turn()

        # If we are second and it's our last turn, countering cannot be accepted -> accept anything >= 0.
        if last and self.me == 1:
            return 0.0

        # Concede over time.
        frac = 0.93 - 0.68 * (p ** 1.18)  # ~0.93 -> ~0.25
        frac = max(0.16, frac)

        # If we are first and it's our last proposal, we must close.
        if last and self.me == 0:
            frac = min(frac, 0.26)

        floor = frac * self.total
        # Avoid dropping too far below best sure option we've seen, unless very late.
        floor = max(floor, self.best_seen - (0.05 + 0.34 * p) * self.total)
        return max(0.0, min(self.total, floor))

    # ------------------------- offer construction -------------------------

    def _base_ask(self) -> list[int]:
        # Ask for all positive-value items; give away items worth 0 to us.
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

    def _dp_min_oppvalue_for_myvalue(self, opp_mu: list[float]):
        """
        Array DP: dp[v] = minimal expected opponent value of items we take (using opp_mu),
        to achieve exact my value v. Reconstructable via prev/take.
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
                for x in range(c + 1):  # x units we take
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
            my[idx] = x
            v = prevs[stage][v] if v >= 0 else 0
        for i in self.zero_types:
            my[i] = 0
        return my

    def _greedy_offer(self, opp_mu: list[float], target_value: int) -> list[int]:
        # Start from keeping all positive-value items, then give away units that are "expensive" to opponent per our value.
        keep = self._base_ask()
        cur = self._my_value(keep)

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

    def _choose_counter(self, their_offer_to_us: list[int] | None):
        if self.total_int <= 0:
            return [0] * self.n, 0.0

        p = self._overall_progress()
        last = self._is_last_our_turn()
        floor = self._my_floor()
        floor_i = int(math.ceil(floor - 1e-9))

        opp_mu = self._mean_opp_unit()

        # Candidate my-values we try to hit (then we pick the best offer by acceptance-aware scoring).
        fracs = [0.99, 0.97, 0.95, 0.92, 0.88, 0.84, 0.80, 0.76, 0.72, 0.68, 0.64, 0.60, 0.56, 0.52, 0.48, 0.44, 0.40, 0.36, 0.32, 0.28, 0.24, 0.20]
        targets = {self.total_int, max(0, min(self.total_int, floor_i))}
        for f in fracs:
            targets.add(int(self.total_int * f))

        if their_offer_to_us is not None:
            v_acc = self._my_value(their_offer_to_us)
            targets.add(v_acc)
            targets.add(min(self.total_int, v_acc + int(0.05 * self.total)))

        cand = {}

        def add(x: list[int]):
            for i in self.zero_types:
                x[i] = 0
            if self._valid_offer(x):
                cand[tuple(x)] = x

        add(self._base_ask())

        # DP when feasible, otherwise greedy generation.
        dp_ok = (self.total_int <= 15000 and sum(self.counts) <= 70 and len(self.pos_types) <= 10)
        if dp_ok:
            types, dp_loss, prevs, takes = self._dp_min_oppvalue_for_myvalue(opp_mu)
            reachable = [v < 1e80 for v in dp_loss]

            # For each target, find best reachable v >= target with minimal opponent loss of our share.
            for t in sorted(targets, reverse=True):
                if not last and t < floor_i:
                    continue
                best_v, best_loss = None, 1e100
                start = max(0, min(self.total_int, t))
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
        min_pacc = 0.06 + 0.22 * p  # demand some plausibility of acceptance; relaxes as p increases

        for off in cand.values():
            myv = self._my_value(off)
            if not last and myv + 1e-9 < floor:
                continue

            pacc = self._p_opp_accept(off)

            # Soft filter early: don't anchor hopelessly.
            if p < 0.40 and pacc < min_pacc:
                continue

            # Encourage convergence toward their last offer (reduces negotiation friction).
            closeness = 0.0
            if their_offer_to_us is not None:
                l1 = sum(abs(off[i] - their_offer_to_us[i]) for i in range(self.n))
                closeness = -(0.010 + 0.030 * p) * self.total * (l1 / max(1, sum(self.counts)))

            # If it's our last proposal (me==0, last), maximize immediate expected value.
            if last and self.me == 0:
                score = myv * pacc + 0.02 * self.total * pacc + closeness
                ev = myv * pacc
            else:
                # Earlier: balance value and acceptability (increasing emphasis on agreement over time).
                w = 0.30 + 0.60 * p
                score = myv * (1.0 - w) + myv * pacc * w
                score += (0.02 + 0.10 * p) * self.total * pacc + closeness
                ev = myv * pacc

            if score > best_score:
                best_score, best, best_ev = score, off, ev

        if best is None:
            best = self._base_ask()
            best_ev = self._my_value(best) * self._p_opp_accept(best)

        return list(best), float(best_ev)

    # ------------------------- main API -------------------------

    def offer(self, o: list[int] | None) -> list[int] | None:
        # If everything is worthless to us, accept anything valid.
        if self.total_int <= 0:
            self.step += 1
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        last = self._is_last_our_turn()

        if o is not None and not self._valid_offer(o):
            # Invalid incoming offer: just propose something.
            counter, _ = self._choose_counter(None)
            self.last_sent = counter
            self.step += 1
            return counter

        # Update beliefs based on observed opponent behavior.
        if o is not None:
            # Their new offer implies our last proposal was rejected (if any).
            self._update_from_rejection_of_last()
            self._update_from_their_offer(o)

            myv_accept = self._my_value(o)
            if myv_accept > self.best_seen:
                self.best_seen = myv_accept

            # If we are second and it's our last turn, countering cannot be accepted.
            if last and self.me == 1:
                self.step += 1
                return None

            floor = self._my_floor()

            counter, counter_ev = self._choose_counter(o)

            # Accept if it meets our floor.
            if myv_accept + 1e-9 >= floor:
                self.step += 1
                return None

            # Very late: avoid zero outcome.
            if self._overall_progress() > 0.90 and myv_accept >= 0.12 * self.total:
                self.step += 1
                return None

            # Compare sure acceptance vs (conservative) immediate expected value of our counter.
            # Early we require a meaningful advantage to justify rejecting.
            p = self._overall_progress()
            margin = (0.08 - 0.05 * p) * self.total  # ~0.08T early, ~0.03T late
            if myv_accept >= counter_ev - margin:
                self.step += 1
                return None

            self.last_sent = counter
            self.step += 1
            return counter

        # We start: propose an anchored but acceptance-aware deal.
        self.last_sent = None
        counter, _ = self._choose_counter(None)
        self.last_sent = counter
        self.step += 1
        return counter