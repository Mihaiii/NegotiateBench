import math
from typing import List, Optional


class Agent:
    """
    Offer semantics (per prompt):
    - Incoming offer `o`: how many items the opponent offers to US (our share).
    - Return None to ACCEPT `o` (only valid if o is not None).
    - Return a list to COUNTER: how many items WE want for ourselves (our share).
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = int(me)
        self.counts = [int(x) for x in counts]
        self.values = [int(v) for v in values]
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        self.turn = 0  # number of OUR turns taken so far
        self.their_offers: List[List[int]] = []
        self.best_seen = 0

        self.pos_idx = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] > 0]
        self.zero_idx = [i for i in range(self.n) if self.counts[i] > 0 and self.values[i] == 0]

        # Offer search space: enumerate all offers if small enough, else use heuristics.
        space = 1
        for i in self.pos_idx:
            space *= (self.counts[i] + 1)
            if space > 140000:
                break
        self._enum_ok = space <= 140000

        # Pre-enumerate offers over positive-value types only (zero-value types always 0 for us).
        self._all_offers = []
        if self._enum_ok and self.total > 0:
            cur = [0] * len(self.pos_idx)

            def rec(k: int):
                if k == len(self.pos_idx):
                    off = [0] * self.n
                    for j, idx in enumerate(self.pos_idx):
                        off[idx] = cur[j]
                    # zero-value types -> 0 kept
                    self._all_offers.append(off)
                    return
                idx = self.pos_idx[k]
                for x in range(self.counts[idx] + 1):
                    cur[k] = x
                    rec(k + 1)

            rec(0)

        self.last_demand = None  # monotone concession guard (my value of last counter)

    # ------------------------- utilities -------------------------

    def _valid_offer(self, o) -> bool:
        if not isinstance(o, (list, tuple)) or len(o) != self.n:
            return False
        for i, x in enumerate(o):
            if not isinstance(x, int):
                return False
            if x < 0 or x > self.counts[i]:
                return False
        return True

    def _my_value(self, my_share: List[int]) -> int:
        return sum(self.values[i] * my_share[i] for i in range(self.n))

    def _overall_progress(self) -> float:
        # overall turn index in [0 .. 2*max_rounds-1]
        if self.max_rounds <= 1:
            return 1.0
        overall = 2 * self.turn + self.me
        denom = 2 * self.max_rounds - 1
        return max(0.0, min(1.0, overall / denom))

    def _is_last_our_turn(self) -> bool:
        return self.turn >= self.max_rounds - 1

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z <= -35.0:
            return 0.0
        if z >= 35.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    # ------------------------- opponent-value estimation -------------------------

    def _opp_unit_estimate(self) -> List[float]:
        """
        Estimate opponent per-unit values (nonnegative) from their offer history:
        - They tend to keep (counts - offer_to_us) what they value.
        - If they concede a type over time, it's weak evidence they value it less.
        Normalize so sum_i counts[i]*mu[i] == self.total.
        """
        if self.total <= 0:
            return [0.0] * self.n

        # Prior: mild preference to spread value.
        score = [0.20] * self.n

        if self.their_offers:
            m = len(self.their_offers)

            kept_mean = [0.0] * self.n
            for off in self.their_offers:
                for i in range(self.n):
                    c = self.counts[i]
                    if c <= 0:
                        continue
                    kept_mean[i] += (c - off[i]) / c
            for i in range(self.n):
                kept_mean[i] /= m

            first = self.their_offers[0]
            last = self.their_offers[-1]
            for i in range(self.n):
                c = self.counts[i]
                if c <= 0:
                    continue
                trend = (last[i] - first[i]) / c  # positive = they give us more over time
                # Keep a lot => higher. Concede more => lower.
                score[i] += 1.30 * kept_mean[i] + 0.55 * max(0.0, -trend) - 0.45 * max(0.0, trend)

        # Give extra (harmless) weight to our own zero-value types: good candidates to hand over.
        for i in self.zero_idx:
            score[i] += 0.55

        # Nonnegative and normalize to exact total.
        for i in range(self.n):
            if self.counts[i] <= 0:
                score[i] = 0.0
            elif score[i] < 0.02:
                score[i] = 0.02

        denom = sum(self.counts[i] * score[i] for i in range(self.n))
        if denom <= 0:
            return [0.0] * self.n
        scale = self.total / denom
        return [score[i] * scale for i in range(self.n)]

    # ------------------------- thresholds -------------------------

    def _their_accept_threshold(self, p: float) -> float:
        # Estimated opponent required value (in THEIR units), as fraction of total.
        # High early, decreases toward end.
        frac = 0.66 - 0.46 * (p ** 1.10)  # ~0.66 -> ~0.20
        return max(0.18, min(0.70, frac)) * self.total

    def _my_floor(self, p: float) -> float:
        if self.total <= 0:
            return 0.0
        last = self._is_last_our_turn()

        # If we're second and it's our last turn, countering can't be accepted.
        if last and self.me == 1:
            return 0.0

        frac = 0.86 - 0.58 * (p ** 1.18)  # ~0.86 -> ~0.28
        frac = max(0.22, frac)
        if last and self.me == 0:
            frac = min(frac, 0.28)  # last proposal: be closeable
        floor = frac * self.total

        # Don't drop far below best_seen unless late.
        floor = max(floor, self.best_seen - (0.08 + 0.34 * p) * self.total)
        return max(0.0, min(self.total, floor))

    # ------------------------- offer generation -------------------------

    def _base_ask(self) -> List[int]:
        # Keep all positive-value items; give away all zero-value items.
        off = [0] * self.n
        for i in range(self.n):
            off[i] = self.counts[i] if self.values[i] > 0 else 0
        return off

    def _greedy_offer_for_constraints(
        self, mu: List[float], my_floor: float, their_floor: float, their_last: Optional[List[int]]
    ) -> List[int]:
        """
        Start with taking all positive-value items, then give away units that
        (a) lose us least, (b) are estimated valuable to them, until constraints satisfied.
        """
        off = self._base_ask()
        myv = self._my_value(off)

        # Build per-unit list for positive-value types: give away best "trade" units first.
        # Higher score -> more attractive to give away.
        units = []
        for i in self.pos_idx:
            if off[i] <= 0:
                continue
            # Prefer to concede units that are valuable to them per our value loss.
            ratio = (mu[i] + 1e-9) / (self.values[i] + 1e-9)
            units.append((ratio, i))
        units.sort(reverse=True)

        def their_value(share_to_us: List[int]) -> float:
            return sum((self.counts[i] - share_to_us[i]) * mu[i] for i in range(self.n))

        # Give away zero-value items already (off[i]=0 for them) - helps their_value by construction.

        # Iterate conceding units while we still meet my_floor and try to meet their_floor.
        # Also gently move toward their_last if provided.
        max_steps = sum(off[i] for i in self.pos_idx)
        for _ in range(max_steps):
            tv = their_value(off)
            if tv + 1e-9 >= their_floor:
                break
            # Pick a unit to concede.
            best_i = None
            best_score = -1e100
            for ratio, i in units:
                if off[i] <= 0:
                    continue
                if myv - self.values[i] < my_floor - 1e-9:
                    continue
                # If their_last exists, prefer conceding types where we currently ask for more than they offered us.
                toward = 0.0
                if their_last is not None:
                    toward = max(0, off[i] - their_last[i]) / max(1, self.counts[i])
                score = ratio + 0.35 * toward
                if score > best_score:
                    best_score = score
                    best_i = i
            if best_i is None:
                break
            off[best_i] -= 1
            myv -= self.values[best_i]

        return off

    def _candidate_offers(self, their_last: Optional[List[int]]) -> List[List[int]]:
        p = self._overall_progress()
        mu = self._opp_unit_estimate()
        my_floor = self._my_floor(p)
        their_floor = self._their_accept_threshold(p)

        cands = {}

        def add(x: List[int]):
            # enforce zero-value types
            for i in self.zero_idx:
                x[i] = 0
            if self._valid_offer(x):
                cands[tuple(x)] = x

        add(self._base_ask())

        if their_last is not None:
            add(list(their_last))
            # Small "meet-in-the-middle": ask for +1 of our best valued type if possible.
            best_i = None
            best_v = -1
            for i in self.pos_idx:
                if their_last[i] < self.counts[i] and self.values[i] > best_v:
                    best_v = self.values[i]
                    best_i = i
            if best_i is not None:
                x = list(their_last)
                x[best_i] += 1
                add(x)

        if self._enum_ok and self._all_offers:
            # Filter enumerated offers to a manageable subset: top by my value and near constraints.
            # We keep many early, fewer late.
            max_keep = int(5000 - 3500 * p)
            max_keep = max(1200, min(5000, max_keep))
            # Pre-score by my value; partial sort by selecting threshold via sampling is overkill; just sort if small.
            # _all_offers size is capped by _enum_ok; worst ~140k, still OK once.
            offers = self._all_offers
            # Sort descending by my value; cache not needed for single session.
            offers = sorted(offers, key=self._my_value, reverse=True)[:max_keep]
            for off in offers:
                add(list(off))
        else:
            # Generate a small ladder of greedy concessions at varying opponent thresholds.
            for f in (1.10, 1.00, 0.92, 0.84, 0.76, 0.68, 0.60):
                add(self._greedy_offer_for_constraints(mu, my_floor, their_floor * f, their_last))
            # Also include slightly more conceding variants (safety for agreement).
            add(self._greedy_offer_for_constraints(mu, my_floor * 0.92, their_floor * 0.80, their_last))

        return list(cands.values())

    def _pick_counter(self, their_last: Optional[List[int]]) -> List[int]:
        p = self._overall_progress()
        last = self._is_last_our_turn()
        mu = self._opp_unit_estimate()

        my_floor = self._my_floor(p)
        their_thr = self._their_accept_threshold(p)
        scale = max(1.0, 0.085 * self.total)

        def their_value(share_to_us: List[int]) -> float:
            return sum((self.counts[i] - share_to_us[i]) * mu[i] for i in range(self.n))

        best_off = None
        best_score = -1e100

        # Plausibility gate: early avoid ultra-low accept probability.
        min_pacc = 0.06 + 0.24 * p

        # Monotone concession: don't increase demand much after conceding.
        max_allowed = None
        if self.last_demand is not None and p > 0.12:
            max_allowed = self.last_demand + int(0.02 * self.total)

        for off in self._candidate_offers(their_last):
            myv = self._my_value(off)
            if not last and myv + 1e-9 < my_floor:
                continue
            if max_allowed is not None and myv > max_allowed:
                continue

            tv = their_value(off)
            pacc = self._sigmoid((tv - their_thr) / scale)

            if p < 0.50 and pacc < min_pacc:
                continue

            dist = 0.0
            if their_last is not None:
                l1 = sum(abs(off[i] - their_last[i]) for i in range(self.n))
                dist = l1 / max(1, sum(self.counts))

            # Score: early focus on my value; late focus on closing.
            w = 0.25 + 0.65 * p
            score = (1 - w) * myv + w * (myv * pacc) + (0.08 + 0.18 * p) * self.total * pacc - (0.03 + 0.07 * p) * self.total * dist

            # Last proposal as first: closing weight.
            if last and self.me == 0:
                score = myv * pacc + 0.35 * self.total * pacc - 0.06 * self.total * dist

            if score > best_score:
                best_score = score
                best_off = off

        if best_off is None:
            best_off = self._base_ask()

        return list(best_off)

    # ------------------------- main API -------------------------

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        # If everything is worthless to us, accept any valid offer; otherwise propose 0.
        if self.total <= 0:
            self.turn += 1
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        last = self._is_last_our_turn()
        p = self._overall_progress()

        # Incoming offer handling
        if o is not None:
            if not self._valid_offer(o):
                # Invalid offer: respond with a sane counter.
                counter = self._pick_counter(self.their_offers[-1] if self.their_offers else None)
                self.last_demand = self._my_value(counter)
                self.turn += 1
                return counter

            self.their_offers.append(list(o))

            myv = self._my_value(o)
            if myv > self.best_seen:
                self.best_seen = myv

            # If we're second and it's our last turn, countering can't be accepted -> accept.
            if last and self.me == 1:
                self.turn += 1
                return None

            # Accept very strong offers immediately.
            if myv >= 0.70 * self.total:
                self.turn += 1
                return None

            floor = self._my_floor(p)

            # Very late: avoid no-deal; accept modest positives.
            if p > 0.92 and myv >= 0.12 * self.total:
                self.turn += 1
                return None

            # Compute counter and compare.
            counter = self._pick_counter(o)
            cv = self._my_value(counter)

            # Accept if it meets our floor.
            if myv + 1e-9 >= floor:
                self.turn += 1
                return None

            # Accept if counter doesn't materially improve (shrinking margin).
            margin = (0.08 - 0.06 * p) * self.total  # early: reject only if meaningful gain
            if myv >= cv - margin:
                self.turn += 1
                return None

            self.last_demand = cv
            self.turn += 1
            return counter

        # We start (o is None): anchor high but with acceptance-awareness.
        counter = self._pick_counter(self.their_offers[-1] if self.their_offers else None)
        self.last_demand = self._my_value(counter)
        self.turn += 1
        return counter