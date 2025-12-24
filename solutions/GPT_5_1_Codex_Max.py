from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – negotiation bot.
    Strategy summary
    ----------------
    - Pre‑enumerate all possible splits when feasible; otherwise use a greedy heuristic.
    - Start ambitious and concede smoothly as turns elapse.
    - Estimate opponent preferences from what they keep/give and bias offers toward
      mutually agreeable splits.
    - Pragmatic acceptance rules: accept sufficiently good offers early, soften late,
      and salvage value on the very last chance.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds            # my total turns in this session
        self.turn = 0                           # my current turn index (1-based)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_items = sum(counts)

        # Opponent value estimate (per item). Start with uniform average per item.
        avg_item = self.total_value / self.total_items if self.total_items else 0
        base = max(0.5, avg_item)
        self.opp_w = [float(base) for _ in range(self.n)]

        # Tracking
        self.best_seen = 0
        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None
        self.stall = 0
        self.keep_counts = [0] * self.n
        self.give_counts = [0] * self.n

        # Precompute all offers if search space is small
        self.candidates: Optional[List[tuple[int, float, List[int]]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 200_000:
                break
        if space <= 200_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            # Sort by my value desc, then estimated opp value desc
            self.candidates.sort(key=lambda x: (-x[0], -x[1]))
            # Keep only best opp_est per my value to trim size
            filtered = []
            seen = set()
            for mv, ov, off in self.candidates:
                if mv in seen:
                    continue
                seen.add(mv)
                filtered.append((mv, ov, off))
            self.candidates = filtered

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

    def _opp_estimate(self, offer: List[int]) -> float:
        # estimated value of what THEY get (complement)
        return sum((self.counts[i] - offer[i]) * self.opp_w[i] for i in range(self.n))

    def _progress(self) -> float:
        # 0.0 at first turn, 1.0 at last own turn
        if self.max_rounds <= 1:
            return 1.0
        return min(1.0, max(0.0, self.turn / self.max_rounds))

    def _accept_threshold(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        # Declines from 0.85 to 0.35 of total; softer on final own turn
        start, end = 0.85, 0.35
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        if last_turn:
            th = min(th, self.total_value * 0.25)
        if self.best_seen > 0:
            th = min(th, max(self.best_seen * 0.95, th))
        return th

    def _target_value(self) -> float:
        # Ambition declines from 0.95 to 0.55 of total; slight stall penalty
        high, low = 0.95, 0.55
        prog = self._progress()
        t = self.total_value * (high - (high - low) * prog)
        t -= 0.04 * self.stall * self.total_value
        t = max(t, self.total_value * 0.35)
        if self.best_seen > 0:
            t = max(t, self.best_seen * 0.97)
        return t

    def _concession_order(self) -> List[int]:
        # Lower ratio => concede earlier; stubborn items push later
        scores = []
        for i in range(self.n):
            stubborn = self.keep_counts[i] + 1
            give = self.give_counts[i] + 1
            stubborn_ratio = stubborn / give
            score = (self.values[i] + 1) / (stubborn_ratio + 0.5)
            scores.append((score, i))
        scores.sort(key=lambda x: (x[0], x[1]))
        return [i for _, i in scores]

    def _select_offer(self, target: float, forbid: Optional[List[int]]) -> List[int]:
        prog = self._progress()
        w_my = 0.9 - 0.35 * prog  # from 0.9 to ~0.55
        chosen = None
        best_score = -1.0

        if self.candidates:
            for mv, ov, off in self.candidates:
                if forbid is not None and off == forbid:
                    continue
                if mv + 1 < target and prog < 0.9:
                    continue
                score = w_my * mv + (1 - w_my) * ov
                if (mv >= target or prog > 0.85) and score > best_score:
                    best_score = score
                    chosen = off
            if chosen is None:
                for mv, ov, off in self.candidates:
                    if forbid is not None and off == forbid:
                        continue
                    score = w_my * mv + (1 - w_my) * ov
                    if score > best_score:
                        best_score = score
                        chosen = off
            return chosen.copy()

        # Greedy fallback
        offer = self.counts.copy()
        cur_val = self._value(offer)
        if cur_val < target:
            return offer
        order = self._concession_order()

        # Give away zero-value items first
        for i in [i for i, v in enumerate(self.values) if v == 0]:
            while offer[i] > 0 and cur_val >= target:
                offer[i] -= 1
                # cur_val unchanged because value is zero

        # Concede cheapest per opp weight
        ratio_order = sorted(order, key=lambda i: (self.values[i] / (self.opp_w[i] + 0.5), self.values[i]))
        for i in ratio_order:
            v = self.values[i]
            while offer[i] > 0 and cur_val - v >= target:
                offer[i] -= 1
                cur_val -= v

        if forbid is not None and offer == forbid:
            for i in ratio_order:
                if offer[i] > 0:
                    offer[i] -= 1
                    break
        return offer

    def _update_opp_from_offer(self, o: List[int]) -> None:
        # Update using what they keep (counts - o)
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            give = o[i]
            if keep > give:
                self.keep_counts[i] += 1
                self.opp_w[i] += 0.6
            else:
                self.give_counts[i] += 1
                self.opp_w[i] = max(0.5, self.opp_w[i] * 0.9)

    # ---------------- core API ----------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If nothing is worth anything, accept immediately
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

        # Salvage: if I'm second and it's my last chance, accept small positive deal
        if o is not None and last_turn and self.me == 1:
            if incoming_val >= max(1, self.total_value * 0.2, self.best_seen * 0.85):
                return None

        # Acceptance logic
        if o is not None:
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            if incoming_val >= self._accept_threshold(last_turn):
                return None
            if self._progress() > 0.75:
                if incoming_val >= max(self.best_seen * 0.95, self.total_value * 0.5):
                    return None
                if incoming_val >= self._target_value() * 0.95 and self._opp_estimate(o) > 0:
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