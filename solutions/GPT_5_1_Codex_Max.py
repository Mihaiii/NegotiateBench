from typing import List, Optional


class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2  # total calls to offer in the whole negotiation
        self.turn = 0  # how many times we've been called
        self.total_value = sum(c * v for c, v in zip(counts, values))
        # Precompute indices sorted by value
        self.idx_asc = sorted(range(len(values)), key=lambda i: values[i])
        self.idx_desc = list(reversed(self.idx_asc))

    def _value_of(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _current_threshold(self) -> float:
        """Acceptance threshold decreases over time."""
        if self.total_turns <= 1:
            return 0
        frac = self.turn / (self.total_turns - 1)
        # Start around 90% of total, linearly down to 10%
        thresh = self.total_value * (0.9 - 0.8 * frac)
        return max(thresh, 0)

    def _build_offer(self, target: float) -> List[int]:
        """Greedy offer: keep items until target value reached, give away low-value items first."""
        offer = self.counts.copy()
        # Give away items worthless to us
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0

        current = self._value_of(offer)
        if current < target:
            # Cannot reach target if we already gave away zero-value items
            offer = self.counts.copy()
            current = self._value_of(offer)

        # Remove low-value items while staying above target
        for i in self.idx_asc:
            v = self.values[i]
            if v <= 0:
                continue
            while offer[i] > 0 and current - v >= target:
                offer[i] -= 1
                current -= v

        # Ensure we are not taking absolutely everything if we can concede one low item
        if offer == self.counts:
            for i in self.idx_asc:
                v = self.values[i]
                if v <= 0 or offer[i] == 0:
                    continue
                if current - v >= target:
                    offer[i] -= 1
                    break
        return offer

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        # Increment turn count
        self.turn += 1

        # If all items are worthless to us, accept anything
        if self.total_value == 0:
            return None if o is not None else [0] * len(self.counts)

        # Value of opponent's offer (what we would get)
        offer_value = self._value_of(o) if o is not None else -1

        # Last turn logic: if this is our final chance to respond, accept any positive value
        last_turn = (self.turn == self.total_turns)
        if o is not None:
            if last_turn and offer_value > 0:
                return None
            # Dynamic acceptance threshold
            if offer_value >= self._current_threshold():
                return None

        # If o is None (first move) or we rejected, build a counter-offer
        target = self._current_threshold()
        # Be slightly ambitious early on
        ambitious_bonus = self.total_value * 0.05
        # Reduce ambition near the end
        frac = self.turn / max(1, self.total_turns - 1)
        ambitious_bonus *= (1.0 - frac)
        target = min(self.total_value, max(0, target + ambitious_bonus))

        return self._build_offer(target)