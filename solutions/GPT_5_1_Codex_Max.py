from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – negotiation bot (improved).
    - Enumerates all allocations when search space is manageable; otherwise uses greedy.
    - Keeps aspiration high early, concedes smoothly toward end.
    - Accepts good incoming offers; salvages a small but nonzero deal on very last turn when second.
    - Chooses counter‑offers that are good for me and look acceptable to the opponent by an estimated model.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me                  # 0 if I start, 1 otherwise
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds  # number of my turns when I start, else also my turns
        self.turn = 0                 # my turns elapsed
        self.total_value = sum(c * v for c, v in zip(counts, values))

        # Opponent preference estimate (inverse of mine as prior, min 1)
        base = (max(values) if values else 0) + 2
        self.opp_w = [max(1, base - v) for v in values]

        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None
        self.best_seen = 0
        self.stall = 0

        # Pre-enumerate feasible offers
        self.candidates: Optional[List[tuple[int, List[int]]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 400_000:
                break
        if space <= 400_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            # Sort by my value desc, then opponent estimate desc
            self.candidates.sort(key=lambda x: (-x[0], -self._opp_estimate(x[1])))
            # Remove dominated (keep top opp_est for each my value)
            filtered = []
            seen_mv = -1
            best_opp = -1
            for mv, off in self.candidates:
                if mv != seen_mv:
                    seen_mv = mv
                    best_opp = -1
                ov = self._opp_estimate(off)
                if ov > best_opp:
                    best_opp = ov
                    filtered.append((mv, off))
            self.candidates = filtered

        # Greedy removal order (cheapest first for me)
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
        return sum((self.counts[i] - offer[i]) * self.opp_w[i] for i in range(self.n))

    def _progress(self) -> float:
        # 0 on my first turn, 1 on my last turn
        if self.max_rounds <= 1:
            return 1.0
        return min(1.0, max(0.0, (self.turn - 1) / (self.max_rounds - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        start, end = 0.88, 0.50
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        floor = 0.30 if last_turn else 0.40
        return max(th, self.total_value * floor)

    def _target_value(self) -> float:
        high, low = 0.95, 0.60
        prog = self._progress()
        extra = min(0.10, 0.03 * self.stall)
        t = self.total_value * (high - (high - low + extra) * prog)
        t = max(t, self.total_value * 0.38)
        if self.best_seen > 0:
            t = max(t, self.best_seen * 0.98)
        return t

    def _select_offer(self, target: float, forbid: Optional[List[int]]) -> List[int]:
        # Use enumerated search if available
        if self.candidates:
            chosen = None
            best_opp = -1
            for mv, off in self.candidates:
                if mv < target:
                    break
                if forbid is not None and off == forbid:
                    continue
                ov = self._opp_estimate(off)
                if ov > best_opp:
                    chosen, best_opp = off, ov
            # If none meets target, pick best my value candidate
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
        # Give away zero-value items
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
        if forbid is not None and offer == forbid:
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
                self.opp_w[i] += keep
            else:
                self.opp_w[i] = max(1, self.opp_w[i] - 1)

    # -------------- core API --------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If I value nothing, accept anything
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

        # If acting second on my last turn: avoid no deal, but don't accept zero
        if o is not None and last_turn and self.me == 1:
            if incoming_val >= max(self.total_value * 0.20, 1):
                return None

        # Acceptance logic
        if o is not None:
            # If they accept my last offer, return None
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            accept_th = self._accept_threshold(last_turn)
            if incoming_val >= accept_th:
                return None
            # If late and offer close to best seen, accept
            if self._progress() > 0.6 and incoming_val >= max(self.best_seen * 0.98, self.total_value * 0.5):
                return None
            # Absolute salvage on final chance already handled above

        # Build counter-offer
        target = self._target_value()
        forbid = o if o is not None else None
        counter = self._select_offer(target, forbid)

        # If identical to their offer, accept to break deadlock
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter