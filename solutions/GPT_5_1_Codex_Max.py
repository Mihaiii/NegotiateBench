from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0  # how many times we have been called
        self.total = sum(c * v for c, v in zip(counts, values))
        self.best_received = 0

        # statistics about what partner tends to give us
        self.offered_sum = [0] * self.n
        self.offered_cnt = 0

        # precompute a manageable set of candidate offers
        self.offers = self._generate_offers(limit=600)

    def _val(self, offer: List[int]) -> int:
        return sum(offer[i] * self.values[i] for i in range(self.n))

    def _generate_offers(self, limit: int) -> List[List[int]]:
        """
        Breadth-first generation of possible allocations to us (starting from taking all),
        limited to at most `limit` different allocations, then sorted by our value descending.
        """
        from collections import deque

        order = sorted(range(self.n), key=lambda i: (self.values[i], self.counts[i]))
        seen = set()
        dq = deque()
        start = tuple(self.counts)
        dq.append(list(start))
        seen.add(start)
        offers: List[List[int]] = []

        while dq and len(offers) < limit:
            cur = dq.popleft()
            offers.append(cur)
            for idx in order:
                if cur[idx] > 0:
                    nxt = cur.copy()
                    nxt[idx] -= 1
                    t = tuple(nxt)
                    if t not in seen:
                        seen.add(t)
                        dq.append(nxt)

        # sort once by our value (desc), then by total items (asc) to prefer smaller bundles
        offers.sort(key=lambda o: (self._val(o), -sum(o)), reverse=True)
        return offers

    def _update_bias(self, o: List[int]) -> None:
        self.offered_cnt += 1
        for i in range(self.n):
            self.offered_sum[i] += o[i]

    def _bias_score(self, off: List[int]) -> float:
        """
        Estimate how much the partner dislikes items we request,
        based on how often they previously offered them to us.
        Higher score => more likely acceptable for partner.
        """
        if self.offered_cnt == 0:
            return 0.0
        return sum(off[i] * (self.offered_sum[i] / self.offered_cnt) for i in range(self.n))

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        # advance our turn counter
        self.turn += 1
        remaining_my_turns = self.max_rounds - self.turn
        # if there is an incoming offer, consider accepting
        if o is not None:
            self._update_bias(o)
            their_val = self._val(o)
            if their_val > self.best_received:
                self.best_received = their_val

            if self.total == 0:
                return None  # nothing to gain anyway

            # acceptance threshold decreases as we approach the end
            progress = (self.turn - 1) / max(1, self.max_rounds - 1)
            ratio = 0.90 - 0.60 * progress  # from 90% down to 30%
            ratio = max(ratio, 0.25)
            min_accept = max(self.best_received, self.total * ratio)

            # on our final decision chance, be more willing to accept something
            if remaining_my_turns == 0:
                min_accept = min_accept * 0.8
                if their_val >= max(self.best_received, self.total * 0.20):
                    return None

            if their_val >= min_accept:
                return None  # accept

        # build a counter offer
        progress = (self.turn - 1) / max(1, self.max_rounds - 1)
        target_ratio = 0.95 - 0.60 * progress  # from 95% down to 35%
        target_ratio = max(target_ratio, 0.35)
        target_value = self.total * target_ratio

        # near the end, aim at least for the best seen so far
        if self.best_received > 0 and remaining_my_turns <= 1:
            target_value = max(target_value, self.best_received)

        chosen = None
        best_val = float('inf')
        best_bias = -1.0

        # prefer the lowest value that still meets target (concession) with highest bias score
        for off in self.offers:
            val = self._val(off)
            if val < target_value:
                continue
            bias = self._bias_score(off)
            if (val < best_val) or (val == best_val and bias > best_bias):
                chosen = off
                best_val = val
                best_bias = bias

        # if none meet the target, pick the highest value offer with best bias
        if chosen is None:
            best_val = -1
            best_bias = -1
            for off in self.offers:
                val = self._val(off)
                bias = self._bias_score(off)
                if (val > best_val) or (val == best_val and bias > best_bias):
                    chosen = off
                    best_val = val
                    best_bias = bias

        return chosen