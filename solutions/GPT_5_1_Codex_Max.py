from typing import List, Optional


class Agent:
    """
    Negotiation agent.
    - Keeps high-value items early, concedes gradually.
    - Gives away items it likely values less (opponent likely values more).
    - Drops acceptance threshold over time; avoids countering on the last word.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = -1
        self.last_offer_made: Optional[List[int]] = None

        self.max_val = max(values) if values else 0
        # Precompute candidates if search space is manageable
        self.candidates = None  # list of tuples (my_val, opp_score, offer)
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 200_000:
                break
        if space <= 200_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            # Sort by high value to us, then higher opponent-score (more plausible for them)
            self.candidates.sort(key=lambda x: (-x[0], -x[1], -sum(x[2])))

        # Fallback sort indices by ascending value (for greedy concessions)
        self.idx_asc = sorted(range(self.n), key=lambda i: self.values[i])

    # ---------- helpers ----------
    def _enumerate(self, idx: int, cur: List[int]) -> None:
        if idx == self.n:
            my_val = self._value_of(cur)
            opp_score = self._opp_score(cur)
            self.candidates.append((my_val, opp_score, cur.copy()))
            return
        for k in range(self.counts[idx] + 1):
            cur[idx] = k
            self._enumerate(idx + 1, cur)
        cur[idx] = 0

    def _value_of(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _opp_score(self, offer: List[int]) -> int:
        """
        Heuristic: items we value less are likely more valuable to opponent.
        Score what we give away using inverse of our value.
        """
        base = self.max_val + 1
        score = 0
        for i in range(self.n):
            give = self.counts[i] - offer[i]
            score += give * (base - self.values[i])
        return score

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        # turn starts at 0, so use (turn-1)/(max_rounds-1) after increment
        return max(0.0, min(1.0, (self.turn - 1) / (self.max_rounds - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        """
        Threshold drops linearly from ~0.95 to ~0.35 of total; extra drop on final turn.
        """
        if self.total_value == 0:
            return 0.0
        start, end = 0.95, 0.35
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        floor = 0.20 if last_turn else 0.25
        th = max(th, self.total_value * floor)
        return th

    def _select_offer(self, target: float) -> List[int]:
        """
        Choose an offer with value >= target if possible, otherwise highest-value offer.
        Prefer offers that look attractive to the opponent (opp_score).
        """
        if self.candidates:
            chosen = None
            for my_val, _, off in self.candidates:
                if my_val >= target:
                    chosen = off
                    break
            if chosen is None:
                chosen = self.candidates[0][2]  # highest value (sorted desc)
            return chosen.copy()

        # Fallback greedy: keep all, remove low-value items while still >= target
        offer = self.counts.copy()
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0
        cur_val = self._value_of(offer)
        if cur_val < target:
            return offer
        for i in self.idx_asc:
            v = self.values[i]
            while offer[i] > 0 and cur_val - v >= target:
                offer[i] -= 1
                cur_val -= v
        return offer

    # ---------- core API ----------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If we value nothing, accept anything or ask for nothing if starting
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        incoming_val = -1
        if o is not None:
            incoming_val = self._value_of(o)
            self.best_seen = max(self.best_seen, incoming_val)

        # If we are second and it's our last turn, we cannot counter (last word risk)
        if o is not None and last_turn and self.me == 1:
            return None  # accept whatever to avoid forced no-deal

        # Decide on acceptance
        if o is not None:
            # If opponent matches our previous offer, accept
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None

            accept_th = self._accept_threshold(last_turn)
            if incoming_val >= accept_th:
                return None
            # Near the end, accept reasonable improvements
            if last_turn and incoming_val > 0:
                return None
            if self.turn >= self.max_rounds - 1 and incoming_val >= max(self.best_seen, accept_th * 0.8):
                return None

        # Build counter-offer
        prog = self._progress()
        ambition = self.total_value * 0.08 * (1.0 - prog)
        target = min(self.total_value, max(0, self._accept_threshold(last_turn) + ambition))

        counter = self._select_offer(target)

        # If counter equals incoming, accept
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter