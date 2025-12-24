from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – streamlined negotiation bot.
    - Enumerates all allocations when feasible; otherwise uses a greedy fallback.
    - Starts with high aspiration, concedes smoothly; protects against no‑deal on the very last turn when second.
    - Accepts good incoming offers; adapts a simple opponent value model from observed keeps/gives.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0

        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_items = sum(counts)

        # Opponent value prior: uniform per item, at least 1
        avg_item = self.total_value / self.total_items if self.total_items else 0
        base = max(1, int(round(avg_item)))
        self.opp_w = [base for _ in range(self.n)]

        self.best_seen = 0
        self.stall = 0
        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None

        # Pre-enumerate offers if space is manageable
        self.candidates: Optional[List[tuple[int, int, List[int]]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 200_000:
                break
        if space <= 200_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            # sort by my value desc, then opp est desc
            self.candidates.sort(key=lambda x: (-x[0], -x[1]))
            # keep only best opp_est for each my value
            filtered = []
            seen = set()
            for mv, ov, off in self.candidates:
                if mv in seen:
                    continue
                seen.add(mv)
                filtered.append((mv, ov, off))
            self.candidates = filtered

        # Greedy removal order (cheapest for me first)
        self.idx_asc = sorted(range(self.n), key=lambda i: (self.values[i], i))

    # ---------------- helpers ----------------
    def _enumerate(self, idx: int, cur: List[int]) -> None:
        if idx == self.n:
            mv = self._value(cur)
            ov = self._opp_estimate(cur)
            self.candidates.append((mv, ov, cur.copy()))
            return
        for k in range(self.counts[idx] + 1):
            cur[idx] = k
            self._enumerate(idx + 1, cur)
        cur[idx] = 0

    def _value(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _opp_estimate(self, offer: List[int]) -> int:
        # estimated value of what THEY get (complement)
        return sum((self.counts[i] - offer[i]) * self.opp_w[i] for i in range(self.n))

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        return min(1.0, max(0.0, (self.turn - 1) / (self.max_rounds - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        # Linear decline from 0.9 to 0.52 of total value
        start, end = 0.90, 0.52
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        # floor a bit higher early, lower late
        floor = self.total_value * (0.45 if last_turn else 0.50)
        return max(th, floor)

    def _target_value(self) -> float:
        high, low = 0.98, 0.60
        prog = self._progress()
        # reduce target if stalled
        stall_penalty = 0.03 * self.stall
        t = self.total_value * (high - (high - low + stall_penalty) * prog)
        t = max(t, self.total_value * 0.45)
        if self.best_seen > 0:
            t = max(t, self.best_seen * 0.99)
        return t

    def _select_offer(self, target: float, forbid: Optional[List[int]]) -> List[int]:
        if self.candidates:
            chosen = None
            best_opp = -1
            for mv, ov, off in self.candidates:
                if mv < target:
                    break
                if forbid is not None and off == forbid:
                    continue
                if ov > best_opp:
                    best_opp = ov
                    chosen = off
            if chosen is None:
                # pick the best my value overall with highest opp est
                top_mv = self.candidates[0][0]
                for mv, ov, off in self.candidates:
                    if mv < top_mv:
                        break
                    if forbid is not None and off == forbid:
                        continue
                    if ov > best_opp:
                        best_opp = ov
                        chosen = off
                if chosen is None:
                    chosen = self.candidates[0][2]
            return chosen.copy()

        # Greedy fallback: start with all items I value
        offer = self.counts.copy()
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0
        cur_val = self._value(offer)
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
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            if keep > 0:
                self.opp_w[i] += keep
            else:
                self.opp_w[i] = max(1, self.opp_w[i] - 1)

    # ---------------- core API ----------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        incoming_val = -1
        if o is not None:
            incoming_val = self._value(o)
            self.best_seen = max(self.best_seen, incoming_val)
            if self.last_offer_from_them is not None and o == self.last_offer_from_them:
                self.stall += 1
            else:
                self.stall = 0
            self.last_offer_from_them = o.copy()
            self._update_opp_from_offer(o)

        # Salvage: if I'm second and it's my last chance, accept a small positive deal
        if o is not None and last_turn and self.me == 1:
            if incoming_val >= max(1, self.total_value * 0.22):
                return None

        # Acceptance logic
        if o is not None:
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            if incoming_val >= self._accept_threshold(last_turn):
                return None
            if self._progress() > 0.75 and incoming_val >= max(self.best_seen * 0.97, self.total_value * 0.55):
                return None

        # Build counter-offer
        target = self._target_value()
        forbid = o if o is not None else None
        counter = self._select_offer(target, forbid)

        # If counter equals their offer, accept to avoid deadlock
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter