from typing import List, Optional


class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.best_received = -1

        # track what partner tends to give us (larger means they likely don't value it)
        self.offered_sum = [0] * self.n
        self.offered_cnt = 0

        # precompute a manageable set of candidate offers
        self.offers = self._generate_offers()

    def _val(self, offer: List[int]) -> int:
        return sum(offer[i] * self.values[i] for i in range(self.n))

    def _generate_offers(self) -> List[List[int]]:
        # start with full set, then breadth-first remove low-value items
        order = sorted(range(self.n), key=lambda i: (self.values[i], self.counts[i]))
        seen = set()
        queue = [list(self.counts)]
        offers = []
        seen.add(tuple(self.counts))
        limit = 400  # keep manageable

        while queue and len(offers) < limit:
            cur = queue.pop(0)
            offers.append(cur)
            for idx in order:
                if cur[idx] > 0:
                    nxt = cur.copy()
                    nxt[idx] -= 1
                    t = tuple(nxt)
                    if t not in seen:
                        seen.add(t)
                        queue.append(nxt)

        offers.sort(key=lambda o: (self._val(o), sum(o)), reverse=True)
        return offers

    def _update_bias(self, o: List[int]) -> None:
        self.offered_cnt += 1
        for i in range(self.n):
            self.offered_sum[i] += o[i]

    def _bias_score(self, off: List[int]) -> float:
        if self.offered_cnt == 0:
            return 0.0
        return sum(off[i] * (self.offered_sum[i] / self.offered_cnt) for i in range(self.n))

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        remaining_rounds = self.max_rounds - self.turn

        # evaluate partner's offer
        if o is not None:
            self._update_bias(o)
            their_val = self._val(o)
            self.best_received = max(self.best_received, their_val)

            # acceptance threshold decreases over time
            progress = (self.turn - 1) / max(1, self.max_rounds - 1)
            threshold = 0.85 - 0.45 * progress  # from 85% to 40%
            if self.me == 1 and remaining_rounds == 0:
                # last chance when we are second: accept almost any positive value
                threshold = 0.2
            if self.total == 0 or their_val >= self.total * threshold:
                return None  # accept

        # build counter-offer
        progress = (self.turn - 1) / max(1, self.max_rounds - 1)
        target = self.total * (0.8 - 0.35 * progress)  # from 80% to 45%

        chosen = None
        best_score = -1.0
        best_val = -1

        # try to pick an offer that meets target and aligns with partner's revealed low-value items
        for off in self.offers:
            val = self._val(off)
            if val < target:
                continue
            score = self._bias_score(off)
            if score > best_score or (score == best_score and val > best_val):
                chosen = off
                best_score = score
                best_val = val

        # if none met target, choose the highest value (with bias tie-break)
        if chosen is None:
            for off in self.offers:
                val = self._val(off)
                score = self._bias_score(off)
                if val > best_val or (val == best_val and score > best_score):
                    best_val = val
                    best_score = score
                    chosen = off

        return chosen