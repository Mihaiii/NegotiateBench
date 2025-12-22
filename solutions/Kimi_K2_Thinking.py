from typing import List, Optional

class Agent:
    """
    A haggling negotiation agent that tries to maximize its own value
    by learning opponent preferences from observed offers and gradually
    conceding as the deadline approaches.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds

        # total number of object types
        self.num_types = len(counts)

        # total number of items per type (sum)
        self.total_items = sum(counts)

        # total value of all objects according to our valuation
        self.total_value = sum(c * v for c, v in zip(counts, values))

        # flag for the degenerate case where everything is worthless to us
        self.zero_value = self.total_value == 0

        # total number of turns that can be taken (2 * rounds)
        self.total_turns = 2 * max_rounds
        self.turns_left = self.total_turns

        # statistics used to estimate opponent valuations
        self.opponent_offer_count = 0
        self.opponent_keep_sum = [0] * self.num_types
        self.opponent_valuations = self._initial_opponent_valuations()

        # best offer we have seen so far (in terms of our own utility)
        self.best_offer_value = 0

    # -----------------------------------------------------------------
    # Helper: initial opponent valuations (uniform over all units)
    def _initial_opponent_valuations(self) -> List[float]:
        if self.zero_value:
            return [0.0] * self.num_types
        # uniform prior: each unit is equally valuable for the opponent
        per_unit = self.total_value / self.total_items
        return [per_unit] * self.num_types

    # -----------------------------------------------------------------
    # Helper: compute current reservation utility for us (declines over time)
    def _reservation_us(self) -> float:
        if self.zero_value:
            return 0.0
        fraction = self.turns_left / self.total_turns
        # reservation goes from 0.8*total down to 0.5*total
        return self.total_value * (0.5 + 0.3 * fraction)

    # -----------------------------------------------------------------
    # Helper: target utility we want to afford the opponent (increases over time)
    def _target_opponent(self) -> float:
        if self.zero_value:
            return 0.0
        fraction = self.turns_left / self.total_turns
        elapsed = 1.0 - fraction          # 0 at start, 1 at deadline
        # target goes from 0.5*total up to 0.8*total
        return self.total_value * (0.5 + 0.3 * elapsed)

    # -----------------------------------------------------------------
    # Helper: compute our utility for a given allocation (what we keep)
    def _our_utility(self, allocation: List[int]) -> int:
        return sum(v * a for v, a in zip(self.values, allocation))

    # -----------------------------------------------------------------
    # Helper: compute opponent's (estimated) utility for a given allocation
    def _opponent_utility(self, allocation: List[int]) -> float:
        # opponent gets the complement of the allocation
        opp = [c - a for c, a in zip(self.counts, allocation)]
        return sum(ov * o for ov, o in zip(self.opponent_valuations, opp))

    # -----------------------------------------------------------------
    # Update opponent valuations from the observed offers
    def _update_opponent_model(self, offer: List[int]) -> None:
        self.opponent_offer_count += 1
        for i in range(self.num_types):
            keep = self.counts[i] - offer[i]
            self.opponent_keep_sum[i] += keep

        if self.opponent_offer_count == 0:
            # no data yet – keep the uniform prior
            return

        # estimate a "preference weight" for each type from the proportion the opponent kept
        weights = []
        for i in range(self.num_types):
            if self.counts[i] == 0:
                weights.append(0.0)
            else:
                prop = self.opponent_keep_sum[i] / (self.opponent_offer_count * self.counts[i])
                # avoid zero weight by adding a tiny epsilon (smooth)
                weights.append(prop + 1e-6)

        # scale weights so that sum_i weights[i] * counts[i] == total_value
        total_weight = sum(w * c for w, c in zip(weights, self.counts))
        if total_weight <= 0:
            # fallback to uniform again (should not happen)
            total_weight = 1.0
        scale = self.total_value / total_weight
        self.opponent_valuations = [w * scale for w in weights]

    # -----------------------------------------------------------------
    # Greedy construction of an allocation that gives the opponent at least
    # `target_opp` utility while keeping as much utility for us as possible.
    def _greedy_allocation(self, target_opp: float) -> List[int]:
        # start by keeping everything
        alloc = self.counts[:]
        opp_val = 0.0

        # priority queue: move items with highest opponent‑gain per unit of our‑loss first.
        # ratio = opponent_value / (our_value + epsilon).  If our_value == 0 the ratio is
        # treated as infinite so those items are moved first.
        ratios = []
        eps = 1e-9
        for i in range(self.num_types):
            if alloc[i] == 0:
                continue
            ov = self.opponent_valuations[i]
            uv = self.values[i]
            if uv == 0:
                ratio = float('inf')
            else:
                ratio = ov / (uv + eps)
            ratios.append((ratio, i))

        # sort by decreasing ratio (best concession first)
        ratios.sort(reverse=True, key=lambda x: x[0])

        # Move items one by one until opponent reaches the target or we run out
        for _, idx in ratios:
            while alloc[idx] > 0 and opp_val < target_opp:
                # move one unit of this type to the opponent
                alloc[idx] -= 1
                opp_val += self.opponent_valuations[idx]
            if opp_val >= target_opp:
                break

        # Even if we moved everything we may not reach the target – that is fine.
        return alloc

    # -----------------------------------------------------------------
    # Main entry point – called each time it is our turn.
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        # one more turn is consumed
        self.turns_left -= 1

        # on the last possible turn we accept any non‑negative offer,
        # because the alternative is zero.
        if self.turns_left == 0 and o is not None:
            if self._our_utility(o) >= 0:
                return None

        reservation = self._reservation_us()
        target_opp = self._target_opponent()

        # -----------------------------------------------------------------
        # If we have received an offer, evaluate it.
        if o is not None:
            our_val = self._our_utility(o)

            # Keep track of the best offer we have ever seen.
            if our_val > self.best_offer_value:
                self.best_offer_value = our_val

            # Accept if the offer meets our current reservation level.
            if our_val >= reservation:
                return None

            # Otherwise reject and update our model of the opponent.
            self._update_opponent_model(o)

        # -----------------------------------------------------------------
        # Produce a counter‑offer.
        # We aim to give the opponent at least `target_opp` (according to our
        # estimate of their valuations).  The greedy algorithm tries to reach
        # that target while keeping as much utility for us as possible.
        # If we have no data about the opponent yet we fall back to a simple
        # uniform prior for the opponent's valuations.
        counter = self._greedy_allocation(target_opp)

        # Ensure the returned list contains only non‑negative integers and respects
        # the original counts (the greedy routine guarantees this).
        return counter