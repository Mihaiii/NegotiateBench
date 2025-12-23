from typing import List, Optional


class Agent:
    """
    Negotiation agent that:
    - Searches all feasible splits when the space is small; otherwise uses a greedy fallback.
    - Starts ambitious and concedes smoothly, with extra concession if the opponent stalls.
    - Learns a crude preference estimate for the opponent from their offers and prefers
      offers that look attractive to them while keeping high value for us.
    - Accepts good offers early and avoids no‑deal on the last word when acting second.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0  # how many times we've been called (our turns only)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = -1
        self.last_offer_made: Optional[List[int]] = None
        self.last_offer_from_them: Optional[List[int]] = None
        self.stall = 0

        max_val = max(values) if values else 0
        base = max_val + 1
        # Initial guess: they like what we like less
        self.opp_pref = [base - v for v in values]

        # Pre-enumerate candidates if feasible
        self.candidates = None  # list of (my_val, opp_score, offer)
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 300_000:
                break
        if space <= 300_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            # Sort: my value desc, opponent score desc
            self.candidates.sort(key=lambda x: (-x[0], -x[1]))

        # Greedy removal order: give away cheapest to us first
        self.idx_asc = sorted(range(self.n), key=lambda i: self.values[i])

    # ---------------- helpers ----------------
    def _enumerate(self, idx: int, cur: List[int]) -> None:
        if idx == self.n:
            my_val = self._value_of(cur)
            opp_score = self._opp_score(cur)
            self.candidates.append((my_val, opp_score, cur.copy()))
            return
        for k in range(self.counts[idx] + 1):
            cur[idx] = k
            self._enumerate(idx + 1, cur)
        cur[idx] = 0

    def _value_of(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _opp_score(self, offer: List[int]) -> int:
        """Heuristic: how attractive to opponent (what we give them, weighted)."""
        score = 0
        for i in range(self.n):
            give = self.counts[i] - offer[i]
            score += give * self.opp_pref[i]
        return score

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        return max(0.0, min(1.0, (self.turn - 1) / (self.max_rounds - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        """Linear drop from ~0.85 to ~0.45 of total, with a floor."""
        if self.total_value == 0:
            return 0.0
        start, end = 0.85, 0.45
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        floor = 0.30 if last_turn else 0.35
        return max(th, self.total_value * floor)

    def _select_offer(self, target: float) -> List[int]:
        """Pick an offer >= target if possible, else best available; prefer opp-attractive."""
        if self.candidates:
            chosen = None
            for my_val, _, off in self.candidates:
                if my_val >= target:
                    chosen = off
                    break
            if chosen is None:
                chosen = self.candidates[0][2]
            return chosen.copy()

        # Greedy fallback: start with everything, give away low-value items while >= target
        offer = self.counts.copy()
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

    def _update_opp_pref_from_offer(self, o: List[int]) -> None:
        """Update heuristic based on what they keep."""
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            if keep > 0:
                self.opp_pref[i] += keep

    # ---------------- core API ----------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If nothing is valuable to us, accept anything / ask nothing
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        incoming_val = -1
        if o is not None:
            incoming_val = self._value_of(o)
            self.best_seen = max(self.best_seen, incoming_val)
            self._update_opp_pref_from_offer(o)
            if self.last_offer_from_them is not None and o == self.last_offer_from_them:
                self.stall += 1
            else:
                self.stall = 0
            self.last_offer_from_them = o.copy()

        # If we are second and it's our last turn, accept anything positive to avoid no-deal
        if o is not None and last_turn and self.me == 1:
            return None

        # Acceptance logic
        if o is not None:
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None
            accept_th = self._accept_threshold(last_turn)
            prog = self._progress()
            # Slightly softer near the end
            soft = accept_th * (0.9 if prog > 0.6 else 1.0)
            if incoming_val >= accept_th:
                return None
            if prog > 0.5 and incoming_val >= max(self.best_seen, self.total_value * 0.55):
                return None
            if incoming_val >= soft and self.stall > 1:
                return None
            if last_turn and incoming_val > 0:
                return None

        # Build counter-offer
        prog = self._progress()
        # Ambition decreases with progress; accelerate concession if stalled
        high, low = 0.95, 0.42
        extra = min(0.15, 0.05 * self.stall)
        target = self.total_value * (high - (high - low + extra) * prog)
        target = max(target, self.total_value * (0.35))
        if self.best_seen > 0:
            target = max(target, self.best_seen * 0.97)

        counter = self._select_offer(target)

        # If counter equals incoming, accept to avoid loops
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter