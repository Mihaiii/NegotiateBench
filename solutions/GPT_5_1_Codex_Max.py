from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0                      # how many times offer() was called for us
        self.total = sum(c * v for c, v in zip(counts, values))
        self.best_received = 0             # best value we have been offered so far

        # statistics about what partner tends to give us (simple frequency average)
        self.offered_sum = [0] * self.n
        self.offered_cnt = 0

        # precompute a manageable set of candidate offers (allocations to ourselves)
        self.offers = self._generate_offers(limit=2000)
        self.last_offer: Optional[tuple] = None  # to avoid exact repetitions

    def _val(self, offer: List[int]) -> int:
        """Compute our value of a given allocation to us."""
        return sum(offer[i] * self.values[i] for i in range(self.n))

    def _generate_offers(self, limit: int) -> List[List[int]]:
        """
        Generate possible allocations (how many of each item we get).
        Limit the number of generated allocations to keep things fast.
        """
        offers: List[List[int]] = []
        stack = [(0, [0] * self.n)]
        while stack and len(offers) < limit:
            idx, cur = stack.pop()
            if idx == self.n:
                offers.append(cur.copy())
                continue
            # explore taking more of valuable items first
            for k in range(self.counts[idx], -1, -1):
                if len(offers) >= limit:
                    break
                nxt = cur.copy()
                nxt[idx] = k
                stack.append((idx + 1, nxt))
        # sort by our value descending, then by fewer items to look less greedy
        offers.sort(key=lambda o: (self._val(o), -sum(o)), reverse=True)
        return offers

    def _update_bias(self, o: List[int]) -> None:
        self.offered_cnt += 1
        for i in range(self.n):
            self.offered_sum[i] += o[i]

    def _bias_score(self, off: List[int]) -> float:
        """
        Estimate how acceptable this offer is to the partner.
        Higher if we request items they have tended to give us.
        """
        if self.offered_cnt == 0:
            return 0.0
        return sum(off[i] * (self.offered_sum[i] / self.offered_cnt) for i in range(self.n))

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        remaining_my_turns = self.max_rounds - self.turn

        # Consider acceptance of partner's offer
        if o is not None:
            self._update_bias(o)
            their_val = self._val(o)
            self.best_received = max(self.best_received, their_val)

            if self.total == 0:
                return None  # nothing to gain, accept

            # acceptance threshold decreases linearly from 90% to 30% of total
            progress = (self.turn - 1) / max(1, self.max_rounds - 1)
            min_ratio = max(0.30, 0.90 - 0.60 * progress)
            min_accept = max(self.best_received, self.total * min_ratio)

            # On our final decision chance, be more lenient
            if remaining_my_turns == 0:
                min_accept = max(self.total * 0.15, min_accept * 0.8)

            if their_val >= min_accept:
                return None  # accept

        # Build a counter-offer
        progress = (self.turn - 1) / max(1, self.max_rounds - 1)
        target_ratio = max(0.35, 0.95 - 0.60 * progress)  # from ~95% down to ~35%
        target_value = self.total * target_ratio
        if self.best_received > 0 and remaining_my_turns <= 1:
            # don't ask for less than best offer seen near the end
            target_value = max(target_value, self.best_received)

        chosen = None
        best_surplus = float('inf')  # how far above target_value
        best_bias = -1.0

        for off in self.offers:
            val = self._val(off)
            if val < target_value:
                continue
            surplus = val - target_value
            bias = self._bias_score(off)
            if (surplus < best_surplus) or (surplus == best_surplus and bias > best_bias):
                chosen = off
                best_surplus = surplus
                best_bias = bias

        # If none meet target_value, pick the offer with highest bias and value
        if chosen is None:
            best_val = -1
            best_bias = -1.0
            for off in self.offers:
                val = self._val(off)
                bias = self._bias_score(off)
                if (val > best_val) or (val == best_val and bias > best_bias):
                    chosen = off
                    best_val = val
                    best_bias = bias

        # avoid repeating the exact same offer if possible (looks stubborn)
        if chosen is not None:
            t = tuple(chosen)
            if self.last_offer == t:
                for off in self.offers:
                    if tuple(off) != self.last_offer:
                        chosen = off
                        break
            self.last_offer = tuple(chosen)
        return chosen