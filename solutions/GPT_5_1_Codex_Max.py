from typing import List, Optional


class Agent:
    """
    GPT 5.1 Codex Max – improved negotiation bot
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        # One call to offer() per round for this agent
        self.max_turns = max_rounds
        self.turn = 0

        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.sum_items = max(1, sum(counts))
        self.best_seen = 0
        self.last_offer: Optional[List[int]] = None

        # Opponent value estimate (initially uniform by average value per item)
        base = (self.total_value / self.sum_items) if self.total_value > 0 else 1.0
        self.opp_w = [float(base) for _ in range(self.n)]

        # Precompute candidates if space manageable
        self.candidates: Optional[List[List[int]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 150_000:
                break
        if space <= 150_000:
            tmp: List[tuple[int, float, List[int]]] = []
            self._enum_offers(0, [0] * self.n, tmp)
            tmp.sort(key=lambda x: (-x[0], -x[1]))
            pareto: List[List[int]] = []
            best_ov = -1.0
            for mv, ov, off in tmp:
                if ov > best_ov:
                    pareto.append(off)
                    best_ov = ov
            # limit to keep selection quick
            self.candidates = pareto[:1000]

    # ---------- helpers ----------
    def _enum_offers(self, idx: int, cur: List[int], acc: List[tuple[int, float, List[int]]]):
        if idx == self.n:
            mv = self._value(cur)
            ov = self._opp_estimate(cur)
            acc.append((mv, ov, cur.copy()))
            return
        for k in range(self.counts[idx] + 1):
            cur[idx] = k
            self._enum_offers(idx + 1, cur, acc)
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
        # Start near 90%, decrease to ~40%
        start, end = 0.9, 0.4
        th = self.total_value * (start - (start - end) * prog)
        if last_turn:
            th = min(th, 0.35 * self.total_value)
        return th

    def _target_value(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        prog = self._progress()
        # Start at full, descend to 0.6; keep 0.5 on last turn
        hi, lo = 1.0, 0.6
        t = self.total_value * (hi - (hi - lo) * prog)
        if last_turn:
            t = max(t, 0.5 * self.total_value)
        return t

    def _concession_order(self) -> List[int]:
        order = []
        for i in range(self.n):
            ratio = (self.values[i] + 0.01) / (self.opp_w[i] + 0.25)
            order.append((ratio, self.values[i], i))
        order.sort(key=lambda x: (x[0], x[1], x[2]))
        return [i for _, _, i in order]

    def _update_opp_from_offer(self, o: List[int]) -> None:
        # If they keep more of an item, raise its estimated value; if they give it, lower.
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            give = o[i]
            if keep > give:
                self.opp_w[i] += 0.6
            elif give > keep:
                self.opp_w[i] = max(0.1, self.opp_w[i] * 0.88)

    def _select_offer(
        self,
        target: float,
        forbid: Optional[List[int]],
        incoming: Optional[List[int]],
    ) -> List[int]:
        prog = self._progress()
        # Mix weight between my value and opponent's estimated value
        alpha = 0.7 - 0.2 * prog  # my weight decreases slightly over time
        beta = 1.0 - alpha
        dist_weight = 0.1 + 0.2 * prog

        chosen: Optional[List[int]] = None
        best_score = -1e18

        def score_offer(off: List[int]) -> float:
            mv = self._value(off)
            ov = self._opp_estimate(off)
            score = alpha * (mv / (self.total_value + 1e-6)) + beta * (ov / (self.total_value + 1e-6))
            if incoming is not None:
                dist = sum(abs(off[i] - incoming[i]) for i in range(self.n))
                score -= dist_weight * dist / self.sum_items
            return score

        # Candidate-based selection
        if self.candidates:
            for off in self.candidates:
                if forbid is not None and off == forbid:
                    continue
                mv = self._value(off)
                if mv + 1e-6 < target * (0.9 if prog > 0.4 else 1.0):
                    continue
                s = score_offer(off)
                if s > best_score:
                    best_score = s
                    chosen = off
            if chosen is not None:
                return chosen.copy()

        # Greedy fallback
        offer = [0] * self.n
        for i, c in enumerate(self.counts):
            offer[i] = c if self.values[i] > 0 else 0
        cur_val = self._value(offer)

        # Concede cheapest to me (relative to opponent) while staying >= target
        for i in self._concession_order():
            while offer[i] > 0 and cur_val - self.values[i] >= target:
                offer[i] -= 1
                cur_val -= self.values[i]

        # If still below target, take missing positives
        if cur_val < target:
            for i in range(self.n):
                while offer[i] < self.counts[i] and cur_val < target:
                    offer[i] += 1
                    cur_val += self.values[i]

        if forbid is not None and offer == forbid:
            for i in self._concession_order():
                if offer[i] > 0:
                    offer[i] -= 1
                    break
        return offer

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
            if self.last_offer is not None and o == self.last_offer:
                return None

        # Acceptance decisions
        if o is not None:
            if incoming_val >= self._accept_threshold(last_turn):
                return None
            # Late: be more willing to take the best seen
            if self._progress() > 0.8 and incoming_val >= max(0.5 * self.total_value, 0.95 * self.best_seen):
                return None
            # Last turn: avoid no-deal
            if last_turn and incoming_val >= max(0.3 * self.total_value, 1):
                return None

        # Build counter-offer
        target = self._target_value(last_turn)
        forbid = o if o is not None else None
        counter = self._select_offer(target, forbid, o)

        # Avoid deadlock: if counter equals incoming, accept instead
        if o is not None and counter == o:
            return None

        self.last_offer = counter
        return counter