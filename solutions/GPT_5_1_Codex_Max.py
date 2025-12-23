from typing import List, Optional


class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds              # how many times we will be called
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = -1                      # best incoming offer value
        self.idx_asc = sorted(range(self.n), key=lambda i: self.values[i])
        self.idx_desc = list(reversed(self.idx_asc))

        # Precompute candidate offers when feasible
        self._candidates = None                  # list of tuples (value, offer)
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 80000:  # safe cap for enumeration
                break
        if space <= 80000 and self.total_value > 0:
            self._candidates = []
            self._enumerate_offers(0, [0] * self.n)
            # Sort by (value desc, items taken asc) to be more conceding on ties
            self._candidates.sort(key=lambda x: (-x[0], sum(x[1])))

    # ----------- helpers ----------- #
    def _enumerate_offers(self, idx: int, current: List[int]) -> None:
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

    def _accept_threshold(self, last_turn: bool) -> float:
        """
        Linearly drop from ~0.95 to ~0.4 of total value, with a floor around 0.35.
        On the very last turn, be more willing (down to ~0.25).
        """
        if self.total_value == 0:
            return 0.0
        start, end = 0.95, 0.40
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        th = max(th, self.total_value * 0.35)
        if last_turn:
            th = min(th, self.total_value * 0.25)
        return th

    def _choose_offer(self, target: float, prog: float) -> List[int]:
        """
        Choose an offer with value >= target, conceding more as prog increases.
        """
        if self._candidates is not None:
            # Candidates are sorted by value descending.
            # Build an ascending list of (value, offer) to pick the smallest >= target.
            for val, off in reversed(self._candidates):
                if val >= target:
                    return off
            # If nothing meets target, concede the best remaining (highest value to us)
            return self._candidates[0][1]

        # Fallback greedy builder if enumeration not available
        offer = self.counts.copy()
        # Give away zero-value items
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0
        current_val = self._value_of(offer)

        # If still below target, take everything
        if current_val < target:
            offer = self.counts.copy()
            current_val = self._value_of(offer)

        # Remove low-value items while staying above target (increasing concession with prog)
        for i in self.idx_asc:
            v = self.values[i]
            if v <= 0:
                continue
            while offer[i] > 0 and current_val - v >= target:
                offer[i] -= 1
                current_val -= v
        return offer

    # ----------- core API ----------- #
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If we value nothing, accept anything (or take nothing if first)
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        # Evaluate incoming offer
        incoming_value = -1
        if o is not None:
            incoming_value = self._value_of(o)
            self.best_seen = max(self.best_seen, incoming_value)

        # Decide acceptance
        if o is not None:
            accept_th = self._accept_threshold(last_turn)
            # More willing on last turn or if offer close to best seen
            if incoming_value >= accept_th:
                return None
            if last_turn and incoming_value > 0:
                return None
            if self.best_seen > 0 and incoming_value >= self.best_seen * 0.95:
                return None

        # Build counter-offer
        prog = self._progress()
        # Ambition bonus shrinks over time
        ambition_bonus = self.total_value * 0.05 * (1.0 - prog)
        target = self._accept_threshold(last_turn) + ambition_bonus
        target = min(self.total_value, max(0, target))
        counter = self._choose_offer(target, prog)

        # If opponent's last offer equals our counter, accept to finalize
        if o is not None and counter == o:
            return None
        return counter