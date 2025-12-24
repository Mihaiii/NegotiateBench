from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – negotiation bot (improved).
    Strategy
    --------
    * Pre-enumerate all feasible splits and keep a Pareto-ish shortlist.
    * Start ambitious, concede smoothly with progress and observed stalling.
    * Estimate opponent taste from their offers (what they keep vs. give).
    * Accept pragmatically: good early offers, softer late and on last chance.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds  # my total turns
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_items = sum(counts)
        self.best_seen = 0
        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None
        self.stall = 0
        self.keep_counts = [0] * self.n
        self.give_counts = [0] * self.n

        # Opponent value estimate
        avg_item = self.total_value / self.total_items if self.total_items else 0.0
        base = max(0.5, avg_item)
        self.opp_w = [float(base) for _ in range(self.n)]

        # Precompute candidates if space small
        self.candidates: Optional[List[tuple[int, float, List[int]]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 200_000:
                break
        if space <= 200_000 and self.total_value > 0:
            tmp = []
            self._enum(0, [0] * self.n, tmp)
            # sort by my value desc then opp_est desc
            tmp.sort(key=lambda x: (-x[0], -x[1]))
            # Keep Pareto-ish shortlist: best opp_est for each my value
            best_for_val = {}
            for mv, ov, off in tmp:
                if mv not in best_for_val:
                    best_for_val[mv] = (mv, ov, off)
            # Keep also top 200 by weighted score to diversify
            top = tmp[:200]
            merged = list(best_for_val.values()) + top
            # Deduplicate
            seen = set()
            cand = []
            for mv, ov, off in merged:
                tup = tuple(off)
                if tup in seen:
                    continue
                seen.add(tup)
                cand.append((mv, ov, off))
            self.candidates = cand

    # ---------- helpers ----------
    def _enum(self, idx: int, cur: List[int], acc: List[tuple]):
        if idx == self.n:
            mv = self._value(cur)
            ov = self._opp_estimate(cur)
            acc.append((mv, ov, cur.copy()))
            return
        for k in range(self.counts[idx] + 1):
            cur[idx] = k
            self._enum(idx + 1, cur, acc)
        cur[idx] = 0

    def _value(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _opp_estimate(self, offer: List[int]) -> float:
        return sum((self.counts[i] - offer[i]) * self.opp_w[i] for i in range(self.n))

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        return min(1.0, max(0.0, self.turn / self.max_rounds))

    def _accept_threshold(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        start, end = 0.85, 0.4
        th = self.total_value * (start - (start - end) * self._progress())
        if last_turn:
            th = min(th, self.total_value * 0.3)
        # do not require more than slightly above best seen
        if self.best_seen > 0:
            th = min(th, max(self.best_seen * 0.95, th))
        return th

    def _target_value(self) -> float:
        hi, lo = 0.95, 0.6
        t = self.total_value * (hi - (hi - lo) * self._progress())
        t -= 0.05 * self.stall * self.total_value
        t = max(t, self.total_value * 0.35)
        if self.best_seen > 0:
            t = max(t, self.best_seen * 0.97)
        return t

    def _concession_order(self) -> List[int]:
        scores = []
        for i in range(self.n):
            stubborn = self.keep_counts[i] + 1
            give = self.give_counts[i] + 1
            ratio = stubborn / give
            score = (self.values[i] + 1) / (ratio + 0.5)
            scores.append((score, i))
        scores.sort(key=lambda x: (x[0], x[1]))
        return [i for _, i in scores]

    def _select_offer(self, target: float, forbid: Optional[List[int]]) -> List[int]:
        prog = self._progress()
        w_my = 0.85 - 0.4 * prog  # 0.85 -> 0.45

        # Use precomputed candidates if available
        if self.candidates:
            chosen = None
            best_score = -1e9
            # First pass: meet target
            for mv, ov, off in self.candidates:
                if forbid is not None and off == forbid:
                    continue
                if mv + 1 < target and prog < 0.9:
                    continue
                score = w_my * mv + (1 - w_my) * ov
                if score > best_score:
                    best_score = score
                    chosen = off
            # Fallback: best overall
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

        # Give away zero-value items immediately
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0
        cur_val = self._value(offer)

        if cur_val <= target:
            return offer

        order = self._concession_order()
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
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            give = o[i]
            if keep > give:
                self.keep_counts[i] += 1
                self.opp_w[i] += 0.5
            else:
                self.give_counts[i] += 1
                self.opp_w[i] = max(0.5, self.opp_w[i] * 0.9)

    # ---------- core ----------
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

        # Salvage on very last chance regardless of role
        if o is not None and last_turn:
            if incoming_val >= max(1, self.total_value * 0.22, self.best_seen * 0.9):
                return None

        # Acceptance logic
        if o is not None:
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            if incoming_val >= self._accept_threshold(last_turn):
                return None
            if self._progress() > 0.75:
                if incoming_val >= max(self.best_seen * 0.9, self.total_value * 0.5):
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