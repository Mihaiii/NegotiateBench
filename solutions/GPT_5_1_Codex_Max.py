from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – negotiation bot (re‑tuned)
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_turns = max_rounds  # number of times offer() can be called
        self.turn = 0

        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = 0
        self.last_offer_made: Optional[List[int]] = None

        # Opponent interest estimate (starts uniform-ish)
        total_items = max(1, sum(counts))
        base = (self.total_value / total_items) if self.total_value > 0 else 1.0
        self.opp_w = [float(base) for _ in range(self.n)]

        # Precompute feasible offers if space is manageable
        self.candidates: Optional[List[tuple[int, float, List[int]]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 300_000:
                break
        if space <= 300_000:
            tmp: List[tuple[int, float, List[int]]] = []
            self._enum(0, [0] * self.n, tmp)
            # Keep a diverse but limited set: pareto on my value then by opp est
            tmp.sort(key=lambda x: (-x[0], -x[1]))
            filtered = []
            best_ov = -1.0
            for mv, ov, off in tmp:
                if ov > best_ov:
                    filtered.append((mv, ov, off))
                    best_ov = ov
            self.candidates = filtered[:600] if len(filtered) > 600 else filtered

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
        # Opponent gets (counts - offer)
        return sum((self.counts[i] - offer[i]) * self.opp_w[i] for i in range(self.n))

    def _progress(self) -> float:
        if self.max_turns <= 1:
            return 1.0
        return min(1.0, max(0.0, (self.turn - 1) / (self.max_turns - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        prog = self._progress()
        start, end = 0.9, 0.45
        th = self.total_value * (start - (start - end) * prog)
        if last_turn:
            th = min(th, 0.35 * self.total_value)
        return th

    def _target_value(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        prog = self._progress()
        hi, lo = 1.0, 0.6
        t = self.total_value * (hi - (hi - lo) * prog)
        if last_turn:
            t = max(t, 0.5 * self.total_value)
        return t

    def _concession_order(self) -> List[int]:
        order = []
        for i in range(self.n):
            ratio = (self.values[i] + 0.01) / (self.opp_w[i] + 0.5)
            order.append((ratio, self.values[i], i))
        order.sort(key=lambda x: (x[0], x[1], x[2]))
        return [i for _, _, i in order]

    def _select_offer(
        self,
        target: float,
        forbid: Optional[List[int]],
        incoming: Optional[List[int]],
    ) -> List[int]:
        prog = self._progress()
        w_my = 0.65 + 0.2 * (1 - prog)  # early: more selfish; late: more balanced
        w_op = 1.0 - w_my
        dist_weight = 0.2 * prog

        if self.candidates:
            chosen = None
            best_score = -1e18
            inc = incoming
            for mv, ov, off in self.candidates:
                if forbid is not None and off == forbid:
                    continue
                # ensure all items allocated: already true by enumeration
                if mv < target and prog < 0.9:
                    continue
                score = w_my * (mv / (self.total_value + 1e-6)) + w_op * (ov / (self.total_value + 1e-6))
                if inc is not None:
                    dist = sum(abs(off[i] - inc[i]) for i in range(self.n))
                    score -= dist_weight * dist / max(1, sum(self.counts))
                if score > best_score:
                    best_score = score
                    chosen = off
            if chosen is None:
                chosen = self.candidates[0][2]
            return chosen.copy()

        # Greedy fallback: start with all useful items, drop cheapest
        offer = [0] * self.n
        for i, c in enumerate(self.counts):
            offer[i] = c if self.values[i] > 0 else 0
        cur_val = self._value(offer)

        if cur_val < target:
            items = []
            for i in range(self.n):
                if self.values[i] > 0 and offer[i] < self.counts[i]:
                    items.append((-self.values[i], i))
            items.sort()
            for _, i in items:
                take = self.counts[i] - offer[i]
                offer[i] += take
                cur_val += take * self.values[i]
                if cur_val >= target:
                    break

        if cur_val > target:
            for i in self._concession_order():
                while offer[i] > 0 and cur_val - self.values[i] >= target:
                    offer[i] -= 1
                    cur_val -= self.values[i]

        if forbid is not None and offer == forbid:
            for i in self._concession_order():
                if offer[i] > 0:
                    offer[i] -= 1
                    break
        return offer

    def _update_opp_from_offer(self, o: List[int]) -> None:
        # If they keep more of an item, raise its estimated value; if they give it, lower.
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            give = o[i]
            if keep > give:
                self.opp_w[i] += 0.5
            elif give > keep:
                self.opp_w[i] = max(0.1, self.opp_w[i] * 0.9)

    # ---------- core ----------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_turns)

        # If I value nothing, accept anything or propose zeros
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        incoming_val = -1
        if o is not None:
            incoming_val = self._value(o)
            self.best_seen = max(self.best_seen, incoming_val)
            self._update_opp_from_offer(o)
            # If they accept my last proposal, end
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None

        # Acceptance decisions
        if o is not None:
            if incoming_val >= self._accept_threshold(last_turn):
                return None
            # Near the end, accept decent deals
            if last_turn and incoming_val > 0:
                # accept if better than best seen and not awful
                if incoming_val >= max(self.best_seen, 0.35 * self.total_value):
                    return None
            # If we are late and offer is OK
            if self._progress() > 0.8 and incoming_val >= 0.5 * self.total_value:
                return None

        # Build counter‑offer
        target = self._target_value(last_turn)
        forbid = o if o is not None else None
        counter = self._select_offer(target, forbid, o)

        # Avoid deadlock: if counter equals incoming, accept instead
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter