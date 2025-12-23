from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – negotiation bot.
    Strategy:
    - Pre‑enumerate all feasible allocations (if space is small) for exact search.
    - Otherwise, use a greedy concession heuristic.
    - Smoothly concedes over time; accepts good incoming offers.
    - Crude opponent modelling from what they keep/give.
    - Avoids deadlock on the last word (especially when acting second).
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0  # number of my turns elapsed
        self.total_value = sum(c * v for c, v in zip(counts, values))

        # Opponent preference weights (initialized as inverse of mine, min 1)
        base = (max(values) if values else 0) + 2
        self.opp_w = [max(1, base - v) for v in values]

        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None
        self.best_seen = 0
        self.stall = 0

        # Pre-enumerate offers if feasible
        self.candidates = None  # list of (my_val, offer)
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 250_000:
                break
        if space <= 250_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            self.candidates.sort(key=lambda x: -x[0])  # by my value desc

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
        # 0 at first my turn, 1 at my last turn
        if self.max_rounds <= 1:
            return 1.0
        return min(1.0, max(0.0, (self.turn) / (self.max_rounds - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        # Linear from 0.88 -> 0.50 of total, with floor
        if self.total_value == 0:
            return 0.0
        start, end = 0.88, 0.50
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        floor = 0.30 if last_turn else 0.35
        return max(th, self.total_value * floor)

    def _target_value(self) -> float:
        # Aspiration from 0.95 -> 0.52, faster if stalled
        high, low = 0.95, 0.52
        prog = self._progress()
        extra = min(0.18, 0.06 * self.stall)
        t = self.total_value * (high - (high - low + extra) * prog)
        t = max(t, self.total_value * 0.35)
        if self.best_seen > 0:
            t = max(t, self.best_seen * 0.96)
        return t

    def _select_offer(self, target: float, forbid: Optional[List[int]]) -> List[int]:
        # Exact search if available
        if self.candidates:
            chosen = None
            best_opp = -1
            # First: offers meeting target
            for mv, off in self.candidates:
                if mv < target:
                    break
                if forbid is not None and off == forbid:
                    continue
                ov = self._opp_estimate(off)
                if ov > best_opp:
                    chosen, best_opp = off, ov
            # None meets target, pick highest mv, then opp_est among top mv
            if chosen is None:
                top_mv = self.candidates[0][0]
                for mv, off in self.candidates:
                    if mv < top_mv:
                        break
                    if forbid is not None and off == forbid:
                        continue
                    ov = self._opp_estimate(off)
                    if ov > best_opp:
                        chosen, best_opp = off, ov
            if chosen is None:
                chosen = self.candidates[0][1]
            return chosen.copy()

        # Greedy fallback
        offer = self.counts.copy()
        # give away zero-value items
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
        # Avoid repeating forbidden
        if forbid is not None and offer == forbid:
            # concede one cheapest unit if possible
            for i in self.idx_asc:
                if offer[i] > 0:
                    offer[i] -= 1
                    break
        return offer

    def _update_opp_from_offer(self, o: List[int]) -> None:
        # Increase weights for items they keep, decrease if they often give away
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            if keep > 0:
                self.opp_w[i] += keep * 2
            else:
                self.opp_w[i] = max(1, self.opp_w[i] - 1)

    # -------------- core API --------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If no value for me, accept anything
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

        # If acting second on my last turn: accept best positive to avoid no deal
        if o is not None and last_turn and self.me == 1:
            if incoming_val > 0:
                return None

        # Acceptance logic
        if o is not None:
            # Accept if they mirrored my last offer
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            accept_th = self._accept_threshold(last_turn)
            if incoming_val >= accept_th:
                return None
            # Late stage: accept if close to best seen and reasonable
            if self._progress() > 0.65 and incoming_val >= max(self.best_seen * 0.97, self.total_value * 0.5):
                return None
            # Final safeguard: if last turn and offer positive
            if last_turn and incoming_val > 0:
                return None

        # Build counter-offer
        target = self._target_value()
        forbid = o if o is not None else None
        counter = self._select_offer(target, forbid)

        # Break deadlock
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter