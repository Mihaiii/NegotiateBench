from typing import List, Optional


class Agent:
    """
    A haggling agent that searches the allocation space when feasible and otherwise
    uses a greedy heuristic. It concedes smoothly over time, learns crude opponent
    preferences from their offers, prefers offers that look acceptable to them, and
    avoids ending with no deal when acting second.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0  # our turns only
        self.total_value = sum(c * v for c, v in zip(counts, values))

        # Opponent preference weights (heuristic)
        # start as inverse of ours to encourage complementarity
        base = (max(values) if values else 0) + 1
        self.opp_w = [base - v for v in values]

        self.best_seen = 0
        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None
        self.stall = 0

        # Pre-enumerate all allocations if space is reasonable
        self.candidates = None  # list of (my_val, offer)
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 250_000:
                break
        if space <= 250_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            # Sort by my value descending
            self.candidates.sort(key=lambda x: -x[0])

        # Greedy removal order (cheapest first)
        self.idx_asc = sorted(range(self.n), key=lambda i: (self.values[i], i))

    # -------------- helpers --------------
    def _enumerate(self, idx: int, cur: List[int]) -> None:
        if idx == self.n:
            mv = self._value_of(cur)
            self.candidates.append((mv, cur.copy()))
            return
        for k in range(self.counts[idx] + 1):
            cur[idx] = k
            self._enumerate(idx + 1, cur)
        cur[idx] = 0

    def _value_of(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _opp_estimate(self, offer: List[int]) -> int:
        # Estimate opponent value of what they keep
        est = 0
        for i in range(self.n):
            keep = self.counts[i] - offer[i]
            est += keep * self.opp_w[i]
        return est

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        return max(0.0, min(1.0, (self.turn - 1) / (self.max_rounds - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        # Linear from 0.82 to 0.47 of total, with floor
        if self.total_value == 0:
            return 0.0
        start, end = 0.82, 0.47
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        floor = 0.30 if last_turn else 0.35
        return max(th, self.total_value * floor)

    def _target_value(self) -> float:
        # Ambition from 0.9 to 0.5, faster concession if stalled
        high, low = 0.90, 0.50
        prog = self._progress()
        extra = min(0.15, 0.05 * self.stall)
        t = self.total_value * (high - (high - low + extra) * prog)
        t = max(t, self.total_value * 0.35)
        if self.best_seen > 0:
            t = max(t, self.best_seen * 0.95)
        return t

    def _select_offer(self, target: float) -> List[int]:
        if self.candidates:
            best = None
            best_opp = -1
            # first pass: offers meeting target
            for mv, off in self.candidates:
                if mv < target:
                    break  # sorted descending by mv
                ov = self._opp_estimate(off)
                if ov > best_opp:
                    best = off
                    best_opp = ov
            if best is None:
                # none meet target; pick highest mv, then opp-est
                mv0, off0 = self.candidates[0]
                best = off0
                best_opp = self._opp_estimate(off0)
                for mv, off in self.candidates:
                    if mv < mv0:
                        break
                    ov = self._opp_estimate(off)
                    if ov > best_opp:
                        best = off
                        best_opp = ov
            return best.copy()

        # Greedy fallback: start with all, give away cheap items while >= target
        offer = self.counts.copy()
        # give away items we value zero
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

    def _update_opp_from_offer(self, o: List[int]) -> None:
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            if keep > 0:
                self.opp_w[i] += keep * 2
            else:
                # slight decay if always given away
                self.opp_w[i] = max(1, self.opp_w[i] - 1)

    # -------------- core API --------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If nothing is valuable, accept anything
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        incoming_val = -1
        if o is not None:
            incoming_val = self._value_of(o)
            self.best_seen = max(self.best_seen, incoming_val)
            self._update_opp_from_offer(o)
            if self.last_offer_from_them is not None and o == self.last_offer_from_them:
                self.stall += 1
            else:
                self.stall = 0
            self.last_offer_from_them = o.copy()

        # If acting second on our last turn, accept anything positive to avoid no-deal
        if o is not None and last_turn and self.me == 1:
            if incoming_val > 0:
                return None

        # Acceptance decisions
        if o is not None:
            # Accept if they matched our previous offer
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            accept_th = self._accept_threshold(last_turn)
            if incoming_val >= accept_th:
                return None
            # If late and incoming is close to best seen, accept
            if self._progress() > 0.6 and incoming_val >= max(self.best_seen * 0.98, self.total_value * 0.5):
                return None
            # Avoid zero on final word
            if last_turn and incoming_val > 0:
                return None

        # Build counter-offer
        target = self._target_value()
        counter = self._select_offer(target)

        # Break loops
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter