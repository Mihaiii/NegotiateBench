from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – revised haggling bot.
    Strategy:
      * Enumerate feasible splits when the space is modest; otherwise, use a guided greedy.
      * Start ambitious, concede smoothly, but keep a firm reservation value.
      * Estimate opponent interest from their offers.
      * Accept only clearly beneficial deals early; soften near the end, and if I move last, salvage any value.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_turns = max_rounds  # my own turns
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = 0
        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None
        self.stall = 0

        # Opponent value estimate (uniform starting prior)
        total_items = sum(counts)
        base = (self.total_value / total_items) if total_items else 1.0
        base = max(0.5, base)
        self.opp_w = [float(base) for _ in range(self.n)]
        self.keep_counts = [0] * self.n
        self.give_counts = [0] * self.n

        # Precompute candidate offers if search space is reasonable
        self.candidates: Optional[List[tuple[int, float, List[int]]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 400_000:
                break
        if self.total_value > 0 and space <= 400_000:
            tmp: List[tuple[int, float, List[int]]] = []
            self._enum(0, [0] * self.n, tmp)
            # Sort by my value desc, opponent est desc
            tmp.sort(key=lambda x: (-x[0], -x[1]))
            # Pareto-ish shortlist: keep best opp est for each distinct my value
            best_for_val = {}
            for mv, ov, off in tmp:
                if mv not in best_for_val or ov > best_for_val[mv][1]:
                    best_for_val[mv] = (mv, ov, off)
            merged = list(best_for_val.values()) + tmp[:300]  # diversify
            seen = set()
            cand = []
            for mv, ov, off in merged:
                t = tuple(off)
                if t in seen:
                    continue
                seen.add(t)
                cand.append((mv, ov, off))
            self.candidates = cand

    # ---------- helpers ----------
    def _enum(self, idx: int, cur: List[int], acc: List[tuple[int, float, List[int]]]):
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
        # What they keep is what they likely value
        return sum((self.counts[i] - offer[i]) * self.opp_w[i] for i in range(self.n))

    def _progress(self) -> float:
        if self.max_turns <= 1:
            return 1.0
        return min(1.0, max(0.0, self.turn / self.max_turns))

    def _accept_threshold(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        prog = self._progress()
        # Linear from 0.98 -> 0.55 of total value
        start, end = 0.98, 0.55
        th = self.total_value * (start - (start - end) * prog)
        # If it's my very last chance (me == 1), salvage anything
        if last_turn and self.me == 1:
            return 0.0
        if last_turn:
            th = min(th, self.total_value * 0.3)
        if self.best_seen > 0:
            th = min(th, self.best_seen * 0.95)
        return th

    def _target_value(self) -> float:
        # Target I aim for in my own offers; smoothly decrease
        hi, lo = 1.0, 0.65
        t = self.total_value * (hi - (hi - lo) * self._progress())
        # If stalled, concede slightly faster
        t -= self.stall * 0.02 * self.total_value
        t = max(t, self.total_value * 0.45)
        if self.best_seen > 0:
            t = max(t, self.best_seen * 0.9)
        return t

    def _concession_order(self) -> List[int]:
        # Lower (value / opp_weight) are conceded first
        order = []
        for i in range(self.n):
            ratio = self.values[i] / (self.opp_w[i] + 0.5)
            order.append((ratio, self.values[i], i))
        order.sort(key=lambda x: (x[0], x[1], x[2]))
        return [i for _, _, i in order]

    def _select_offer(self, target: float, forbid: Optional[List[int]]) -> List[int]:
        prog = self._progress()
        # Blend weight on my value vs estimated opponent satisfaction
        w_my = 0.85 - 0.3 * prog  # decreases over time

        # Use precomputed candidates if available
        if self.candidates:
            chosen = None
            best_score = -1e18
            for mv, ov, off in self.candidates:
                if forbid is not None and off == forbid:
                    continue
                if mv < target and prog < 0.95:
                    continue
                score = w_my * mv + (1 - w_my) * ov
                if score > best_score:
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

        # Greedy fallback for large spaces
        offer = [c for c in self.counts]
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0  # give away worthless items
        cur_val = self._value(offer)
        if cur_val <= target:
            return offer

        order = self._concession_order()
        for i in order:
            v = self.values[i]
            while offer[i] > 0 and cur_val - v >= target:
                offer[i] -= 1
                cur_val -= v
            if cur_val <= target:
                break

        if forbid is not None and offer == forbid:
            for i in order:
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
                self.opp_w[i] += 0.35
            else:
                self.give_counts[i] += 1
                self.opp_w[i] = max(0.35, self.opp_w[i] * 0.92)

    # ---------- core ----------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_turns)

        # If nothing is valuable to me, accept anything
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

        # If I move second and this is my last chance, take the best we can get now
        if o is not None and last_turn and self.me == 1:
            return None  # accept any value (nonnegative)

        # Early acceptance of very good offers
        if o is not None:
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            if incoming_val >= self._accept_threshold(last_turn):
                return None

        # Build counter-offer
        target = self._target_value()
        forbid = o if o is not None else None
        counter = self._select_offer(target, forbid)

        # Avoid deadlock; if equal to their offer, accept instead
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter