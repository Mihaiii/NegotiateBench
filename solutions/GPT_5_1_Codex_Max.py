from typing import List, Optional


class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds          # how many times WE will be called
        self.turn = 0                         # how many times offer() has been called
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = -1                   # best offer value seen so far
        self.idx_asc = sorted(range(self.n), key=lambda i: self.values[i])
        self.idx_desc = list(reversed(self.idx_asc))

        # Precompute manageable offer space
        self._candidates = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 50000:  # cap enumeration
                break
        if space <= 50000 and self.total_value > 0:
            self._candidates = []
            self._enumerate_offers(0, [0] * self.n)
            # sort by (value desc, items_taken asc to be more conceding)
            self._candidates.sort(key=lambda x: (-x[0], sum(x[1])))

    def _enumerate_offers(self, idx: int, current: List[int]):
        if idx == self.n:
            val = self._value_of(current)
            self._candidates.append((val, current.copy()))
            return
        for k in range(self.counts[idx] + 1):
            current[idx] = k
            self._enumerate_offers(idx + 1, current)
        current[idx] = 0

    def _value_of(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        return (self.turn - 1) / (self.max_rounds - 1)

    def _accept_threshold(self) -> float:
        # Linearly decrease from 0.9 to 0.3 of total value
        start, end = 0.9, 0.3
        return self.total_value * (start - (start - end) * self._progress())

    def _choose_offer(self, target: float) -> List[int]:
        # If we have enumerated candidates, choose a minimally sufficient one
        if self._candidates is not None:
            for val, off in reversed(self._candidates):
                # reversed because sorted by value desc, so reversed gives low to high
                if val >= target:
                    return off
            # otherwise, take the highest value available
            return self._candidates[0][1]

        # Fallback greedy builder
        offer = self.counts.copy()
        # Give away zero-value items first
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0
        current = self._value_of(offer)
        if current < target:
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
        # If still equal to all, concede one lowest positive if possible
        if offer == self.counts:
            for i in self.idx_asc:
                v = self.values[i]
                if v > 0 and offer[i] > 0 and current - v >= target:
                    offer[i] -= 1
                    break
        return offer

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1

        # If we value nothing, accept anything
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        if o is not None:
            val = self._value_of(o)
            if val > self.best_seen:
                self.best_seen = val
        else:
            val = -1

        last_turn = (self.turn == self.max_rounds)

        # Acceptance decision
        if o is not None:
            # Be more willing to accept on the final turn
            if last_turn and val > 0:
                return None
            # General threshold
            if val >= self._accept_threshold():
                return None

        # Build counter-offer
        # Ambition bonus decreases over time
        ambition_bonus = self.total_value * 0.05 * (1.0 - self._progress())
        target = max(0, min(self.total_value, self._accept_threshold() + ambition_bonus))
        return self._choose_offer(target)