import math
from typing import List, Optional


class Agent:
    """
    Heuristic bargaining agent under unknown opponent valuations with known equal total value.

    Core ideas:
    - Estimate opponent "preferences" from what they keep in their offers.
    - Convert preference weights into a pseudo valuation vector scaled to match our known total.
    - Make offers by keeping at least a target value for ourselves while giving away items
      that (a) cost us little and (b) seem to matter to them.
    - Accept offers above a time-dependent threshold.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = int(me)
        self.counts = list(counts)
        self.values = list(values)
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # Called once per our turn; starts at 0.
        self.turn_idx = 0

        # Best value we have been offered so far (from our perspective).
        self.best_received = 0

        # Opponent preference weights (higher => they likely value it more).
        # Start slightly >0 to avoid zeros.
        self.opp_pref = [1.0] * self.n

        # Precompute for speed.
        self._all_zero_offer = [0] * self.n

    # ------------------------- Utility helpers -------------------------

    def _my_value(self, offer_to_me: List[int]) -> int:
        return sum(v * x for v, x in zip(self.values, offer_to_me))

    def _progress(self) -> float:
        # 0.0 at our first move, 1.0 at our last move
        if self.max_rounds <= 1:
            return 1.0
        return min(1.0, max(0.0, self.turn_idx / (self.max_rounds - 1)))

    @staticmethod
    def _sigmoid(x: float) -> float:
        # Numerically safe logistic
        if x < -20:
            return 0.0
        if x > 20:
            return 1.0
        return 1.0 / (1.0 + math.exp(-x))

    def _update_opp_pref(self, o: List[int]) -> None:
        # Opponent keeps (counts - o). Accumulate what they keep over time.
        for i in range(self.n):
            kept = self.counts[i] - o[i]
            if kept > 0:
                self.opp_pref[i] += kept

    def _opp_unit_values_scaled(self) -> List[float]:
        # Scale weights so that sum(counts[i] * opp_unit[i]) == our total.
        # If our total == 0, any scale works; return zeros.
        if self.total <= 0:
            return [0.0] * self.n
        denom = sum(self.counts[i] * self.opp_pref[i] for i in range(self.n))
        if denom <= 0:
            return [0.0] * self.n
        scale = self.total / denom
        return [w * scale for w in self.opp_pref]

    def _opp_est_value(self, offer_to_me: List[int], opp_unit: List[float]) -> float:
        # Estimated opponent value of their share.
        return sum((self.counts[i] - offer_to_me[i]) * opp_unit[i] for i in range(self.n))

    # ------------------------- Offer construction -------------------------

    def _build_offer_greedy(self, target_my_value: float, opp_unit: List[float]) -> List[int]:
        """
        Start from taking everything, then concede units that maximize opponent gain per our loss,
        while keeping my_value >= target_my_value. Always give away our zero-value items.
        """
        offer = self.counts[:]  # we take all
        my_val = self.total

        # Give away all items we don't value.
        for i in range(self.n):
            if self.values[i] == 0 and offer[i] > 0:
                offer[i] = 0

        # Recompute after zero-value giveaways.
        my_val = self._my_value(offer)
        if my_val <= target_my_value or self.total <= 0:
            return offer

        # Sort item-types by "opponent value per our cost" (descending).
        items = []
        for i in range(self.n):
            if offer[i] > 0 and self.values[i] > 0:
                ratio = opp_unit[i] / self.values[i]  # higher => better to give
                items.append((ratio, i))
        items.sort(reverse=True)

        # Concede as much as possible from best ratios while staying above target.
        for _, i in items:
            if my_val <= target_my_value:
                break
            v = self.values[i]
            if v <= 0 or offer[i] <= 0:
                continue
            # max units we can give without dropping below target
            slack = my_val - target_my_value
            give = int(min(offer[i], slack // v))
            if give > 0:
                offer[i] -= give
                my_val -= give * v

        return offer

    # ------------------------- Decision logic -------------------------

    def _accept_threshold(self) -> float:
        """
        Time-dependent acceptance threshold (fraction of total).
        Starts firm and concedes over time.
        """
        if self.total <= 0:
            return 0.0

        p = self._progress()

        # Base schedule: 0.75 -> 0.25
        frac = 0.75 - 0.50 * p

        # If we are second, our last move is final; keep some minimum, but not too high.
        if self.me == 1 and self.turn_idx >= self.max_rounds - 1:
            frac = min(frac, 0.30)  # last chance to accept; be pragmatic

        # If we are first, our last move is an offer (opponent still responds),
        # so acceptance can remain a touch firmer.
        if self.me == 0 and self.turn_idx >= self.max_rounds - 1:
            frac = max(frac, 0.35)

        # Don't accept far below our best seen unless very late.
        best_guard = self.best_received - 0.05 * self.total
        return max(frac * self.total, best_guard)

    def _choose_counter_offer(self) -> List[int]:
        """
        Select an offer maximizing expected utility = my_value * P(accept),
        where P(accept) is estimated from opponent pseudo-value and a time-dependent threshold.
        """
        if self.total <= 0:
            return self._all_zero_offer[:]

        p = self._progress()
        opp_unit = self._opp_unit_values_scaled()

        # Opponent "likely accept" threshold (estimated): 0.65 -> 0.35 of total
        opp_th = (0.65 - 0.30 * p) * self.total
        opp_k = max(1.0, 0.10 * self.total)  # softness

        # Our target for counter-offers: start high, concede toward our acceptance threshold.
        accept_val = self._accept_threshold()
        start_target = (0.92 - 0.42 * p) * self.total  # 0.92 -> 0.50
        start_target = max(start_target, accept_val + 0.02 * self.total)

        # Explore a few target levels.
        targets = []
        t = start_target
        step = 0.05 * self.total
        for _ in range(8):
            targets.append(max(accept_val, t))
            t -= step
            if t <= accept_val:
                break
        targets.append(accept_val)

        best_offer = None
        best_score = -1e18

        for tgt in targets:
            offer = self._build_offer_greedy(tgt, opp_unit)
            myv = self._my_value(offer)
            oppv = self._opp_est_value(offer, opp_unit)

            # Acceptance probability model
            prob = self._sigmoid((oppv - opp_th) / opp_k)

            # Slightly favor deals that are more acceptable to them (tie-breaker)
            score = myv * prob + 0.01 * oppv

            if score > best_score:
                best_score = score
                best_offer = offer

        return best_offer if best_offer is not None else self._build_offer_greedy(accept_val, opp_unit)

    # ------------------------- Public API -------------------------

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        # Advance our internal turn counter at the start of our move.
        # (We use turn_idx in thresholds, and it should reflect "this move".)
        idx = self.turn_idx
        self.turn_idx += 1

        # Validate and process opponent offer (if present).
        if o is not None:
            if (
                not isinstance(o, list)
                or len(o) != self.n
                or any((not isinstance(x, int)) for x in o)
                or any(x < 0 or x > self.counts[i] for i, x in enumerate(o))
            ):
                # Invalid input from environment/opponent; play safe: make a valid offer.
                return self._choose_counter_offer()

            self._update_opp_pref(o)

            v = self._my_value(o)
            if v > self.best_received:
                self.best_received = v

            if v >= self._accept_threshold():
                return None  # accept

            # If we are second and this was our last move, rejecting ends talks anyway.
            # In that case, accept if it meets a minimal practical floor (to avoid pure 0 deals).
            if self.me == 1 and idx >= self.max_rounds - 1:
                floor = 0.20 * self.total
                if self.total <= 0 or v >= floor:
                    return None
                # else: we counter (equivalent to no deal), but return a valid offer.
                return self._choose_counter_offer()

        # No offer to accept (either first move or we reject): make a counter-offer.
        return self._choose_counter_offer()