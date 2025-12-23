from typing import List, Optional


class Agent:
    """
    Negotiation agent:
    - Enumerates feasible splits when possible, otherwise uses a greedy fallback.
    - Starts ambitious, concedes smoothly; accepts decent offers earlier if already good.
    - Tries to hand over items it likely values less / opponent values more.
    - Avoids ending with no-deal (accepts on last word when second).
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0  # how many times we've been called
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = -1
        self.last_offer_made: Optional[List[int]] = None

        self.max_val = max(values) if values else 0

        # Opponent preference heuristic (updated from their offers)
        # Initialized inversely proportional to our value (items we value less are probably
        # more valuable to them).
        base = self.max_val + 1
        self.opp_pref = [base - v for v in values]

        # Precompute all feasible offers if the search space is manageable
        self.candidates = None  # list of tuples (my_val, opp_score, offer)
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 300_000:  # modest cap for speed
                break
        if space <= 300_000 and self.total_value > 0:
            self.candidates = []
            self._enumerate(0, [0] * self.n)
            # Sort by my value desc, opp_score desc
            self.candidates.sort(key=lambda x: (-x[0], -x[1]))

        # Greedy concession order: ascending by my value
        self.idx_asc = sorted(range(self.n), key=lambda i: self.values[i])

    # ----------------- helpers -----------------
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
        """Heuristic attractiveness to opponent: what we give them weighted by opp_pref."""
        score = 0
        for i in range(self.n):
            give = self.counts[i] - offer[i]
            score += give * self.opp_pref[i]
        return score

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        # turn starts at 0; use (turn - 1)/(max_rounds - 1) after increment
        return max(0.0, min(1.0, (self.turn - 1) / (self.max_rounds - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        """
        Linear drop from ~0.90 to ~0.45 of total. Extra softness near the end.
        """
        if self.total_value == 0:
            return 0.0
        start, end = 0.90, 0.45
        prog = self._progress()
        th = self.total_value * (start - (start - end) * prog)
        floor = 0.30 if last_turn else 0.35
        return max(th, self.total_value * floor)

    def _select_offer(self, target: float) -> List[int]:
        """
        Choose an offer with value >= target if possible, otherwise highest-value offer.
        Prefer offers attractive to opponent.
        """
        if self.candidates:
            # Because candidates sorted by my_val desc then opp_score desc,
            # find first meeting target; otherwise best overall
            chosen = None
            for my_val, _, off in self.candidates:
                if my_val >= target:
                    chosen = off
                    break
            if chosen is None:
                chosen = self.candidates[0][2]
            return chosen.copy()

        # Fallback greedy: start with all, remove low-value items while staying >= target
        offer = self.counts.copy()
        # Give away items we value at 0 immediately
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
        """
        Update heuristic preference based on what opponent kept for themselves.
        The more they keep of an item, the more we think they value it.
        """
        for i in range(self.n):
            them_take = self.counts[i] - o[i]
            # Increment modestly to avoid runaway scaling
            self.opp_pref[i] += them_take

    # ----------------- core API -----------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_rounds)

        # If we value nothing, accept anything or ask for nothing if starting
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        incoming_val = -1
        if o is not None:
            incoming_val = self._value_of(o)
            self.best_seen = max(self.best_seen, incoming_val)
            # Learn about opponent preferences
            self._update_opp_pref_from_offer(o)

        # If we are second and it's our last turn, we cannot counter (avoid no-deal)
        if o is not None and last_turn and self.me == 1:
            return None

        # Decide on acceptance
        if o is not None:
            # If opponent matches our previous offer, accept
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None

            accept_th = self._accept_threshold(last_turn)
            # Accept if meets threshold
            if incoming_val >= accept_th:
                return None
            # Accept if clearly the best we've seen and not terrible
            if incoming_val >= max(self.best_seen, self.total_value * 0.5):
                return None
            # Near the end, accept reasonable positive offers
            if last_turn and incoming_val > 0:
                return None
            if self.turn >= self.max_rounds - 1 and incoming_val >= max(self.best_seen, accept_th * 0.8):
                return None

        # Build counter-offer
        prog = self._progress()
        # Ambition decreases with progress; never below 40% total
        target = self.total_value * (0.90 - 0.40 * prog)
        target = max(target, self.total_value * 0.40)
        # If we've seen something good, don't go below it by much
        if self.best_seen > 0:
            target = max(target, self.best_seen * 0.97)

        counter = self._select_offer(target)

        # If counter equals incoming, accept to avoid loops
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter