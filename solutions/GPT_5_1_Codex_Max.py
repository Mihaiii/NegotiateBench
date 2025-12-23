from typing import List, Optional


class Agent:
    """
    Negotiation agent that aims to keep high-value items, concedes gradually,
    and avoids accepting poor early offers.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds          # how many times we will be called
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = -1                   # best incoming offer value so far

        # Sort indices by increasing item value (useful for concessions)
        self.idx_asc = sorted(range(self.n), key=lambda i: self.values[i])

        # Precompute all possible offers if feasible
        self.candidates = None                # list of tuples (value, offer)
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 200_000:               # safe cap for enumeration
                break
        if space <= 200_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            # Sort ascending by value (and by fewer items kept for extra concession)
            self.candidates.sort(key=lambda x: (x[0], sum(x[1])))

    # ----------- helpers ----------- #
    def _enumerate(self, idx: int, cur: List[int]) -> None:
        if idx == self.n:
            val = self._value_of(cur)
            self.candidates.append((val, cur.copy()))
            return
        for k in range(self.counts[idx] + 1):
            cur[idx] = k
            self._enumerate(idx + 1, cur)
        cur[idx] = 0

    def _value_of(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _progress(self) -> float:
        """
        0.0 at first turn, 1.0 at our last turn.
        """
        if self.max_rounds <= 1:
            return 1.0
        return (self.turn) / self.max_rounds

    def _accept_threshold(self, last_turn: bool) -> float:
        """
        Linearly drops from ~0.9 to ~0.3 of total value.
        Be more lenient on the very last turn (down to ~0.2).
        """
        if self.total_value == 0:
            return 0.0
        start, end = 0.90, 0.30
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        th = max(th, self.total_value * 0.20 if last_turn else self.total_value * 0.25)
        return th

    def _choose_offer(self, target: float) -> List[int]:
        """
        Choose an offer with value >= target if possible, otherwise best offer.
        Uses precomputed candidates when available, else a greedy builder.
        """
        if self.candidates:
            # candidates sorted ascending by value
            chosen = None
            for val, off in self.candidates:
                if val >= target:
                    chosen = off
                    break
            if chosen is None:
                chosen = self.candidates[-1][1]  # highest value to us
            return chosen.copy()

        # Fallback greedy builder: start with all, drop lowest-value items while above target
        offer = self.counts.copy()
        # Give away items we value at 0 immediately
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0
        cur_val = self._value_of(offer)
        if cur_val < target:
            return offer

        for i in self.idx_asc:
            v = self.values[i]
            if v <= 0:
                continue
            while offer[i] > 0 and cur_val - v >= target:
                offer[i] -= 1
                cur_val -= v
        return offer

    # ----------- core API ----------- #
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If we value nothing, accept anything or offer nothing if starting
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        incoming_value = -1
        if o is not None:
            incoming_value = self._value_of(o)
            if incoming_value > self.best_seen:
                self.best_seen = incoming_value

        # Decide acceptance
        if o is not None:
            accept_th = self._accept_threshold(last_turn)
            # Primary acceptance rule
            if incoming_value >= accept_th:
                return None
            # If last turn, accept any positive offer to avoid getting nothing
            if last_turn and incoming_value > 0:
                return None
            # If incoming improves the best seen significantly near the end, accept
            if self.turn >= self.max_rounds - 1 and incoming_value >= max(self.best_seen, accept_th * 0.8):
                return None

        # Build counter-offer
        prog = self._progress()
        # Ambition shrinks over time
        ambition_bonus = self.total_value * 0.05 * (1.0 - prog)
        target = self._accept_threshold(last_turn) + ambition_bonus
        target = min(self.total_value, max(0, target))

        counter = self._choose_offer(target)

        # If the counter equals the incoming offer, accept to finalize
        if o is not None and counter == o:
            return None
        return counter