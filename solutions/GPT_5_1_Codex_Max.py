from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – refined negotiation bot.
    - Enumerates feasible splits to search jointly good offers.
    - Learns opponent inclination from their keeps/gives to shape concessions.
    - Ambitious start, smooth concession, pragmatic late acceptance / salvage.
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

        # Opponent value prior: uniform per item (at least 1)
        avg_item = self.total_value / self.total_items if self.total_items else 0
        base = max(1.0, round(avg_item))
        self.opp_w = [base for _ in range(self.n)]

        # Tracking
        self.best_seen = 0
        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None
        self.stall = 0
        self.keep_counts = [0] * self.n
        self.give_counts = [0] * self.n

        # Pre-enumerate offers if space manageable
        self.candidates: Optional[List[tuple[int, float, List[int]]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 300_000:
                break
        if space <= 300_000 and self.total_value > 0:
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
        if self.max_rounds <= 1:
            return 1.0
        return min(1.0, max(0.0, (self.turn - 1) / (self.max_rounds - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        # Decline from 0.95 to 0.45; extra softness on final own turn
        start, end = 0.95, 0.45
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        if last_turn:
            th = min(th, self.total_value * 0.35)
        return th

    def _target_value(self) -> float:
        # Ambitious to moderate over time, with stall-based reduction
        high, low = 1.00, 0.55
        prog = self._progress()
        t = self.total_value * (high - (high - low) * prog)
        t -= 0.05 * self.stall * self.total_value
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
        scores.sort(key=lambda x: (x[0], x[1]))  # low score => easier to concede
        return [i for _, i in scores]

    def _select_offer(self, target: float, forbid: Optional[List[int]]) -> List[int]:
        prog = self._progress()
        w_my = 0.85 - 0.25 * prog  # from 0.85 down to ~0.60
        chosen = None
        best_score = -1.0

        if self.candidates:
            for mv, ov, off in self.candidates:
                if forbid is not None and off == forbid:
                    continue
                if mv + 1 < target and prog < 0.9:
                    continue
                score = w_my * mv + (1 - w_my) * ov
                if (mv >= target or prog > 0.8) and score > best_score:
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

        # Greedy fallback using concession order and value / opp_weight ratio
        offer = self.counts.copy()
        cur_val = self._value(offer)
        if cur_val < target:
            return offer
        order = self._concession_order()
        # If we have any zero-value items, give them up first
        zero_indices = [i for i, v in enumerate(self.values) if v == 0]
        for i in zero_indices:
            while offer[i] > 0 and cur_val >= target:
                offer[i] -= 1
        cur_val = self._value(offer)
        # Now concede cheapest per opp weight
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
                self.opp_w[i] += 0.5
            else:
                self.give_counts[i] += 1
                self.opp_w[i] = max(0.5, self.opp_w[i] * 0.9)

    # ---------------- core API ----------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If nothing is worth anything, trivially accept
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
            if incoming_val >= max(1, self.total_value * 0.20, self.best_seen * 0.85):
                return None

        # Acceptance logic
        if o is not None:
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            if incoming_val >= self._accept_threshold(last_turn):
                return None
            if self._progress() > 0.75:
                if incoming_val >= max(self.best_seen * 0.95, self.total_value * 0.50):
                    return None
                if incoming_val >= self._target_value() * 0.94 and self._opp_estimate(o) > 0:
                    return None
            if last_turn and incoming_val > 0:
                # If this is truly the last word, better something than nothing
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