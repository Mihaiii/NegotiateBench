from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.offers = self._generate_offers()

    # compute my valuation of an offer
    def _val(self, offer: List[int]) -> int:
        return sum(offer[i] * self.values[i] for i in range(len(offer)))

    # generate a manageable, diverse set of offers, biased toward keeping high-value items
    def _generate_offers(self) -> List[List[int]]:
        n = len(self.counts)
        order = sorted(range(n), key=lambda i: self.values[i])  # remove low-value items first
        seen = set()
        offers = []

        start = tuple(self.counts)
        queue = [list(start)]
        seen.add(start)
        offers.append(list(start))

        # breadth-first removal of items, limiting total offers to keep things fast
        while queue and len(offers) < 2000:
            cur = queue.pop(0)
            for idx in order:
                if cur[idx] > 0:
                    nxt = cur.copy()
                    nxt[idx] -= 1
                    t = tuple(nxt)
                    if t not in seen:
                        seen.add(t)
                        offers.append(nxt)
                        queue.append(nxt)

        # sort offers by my value (desc), then by total items kept (desc)
        offers.sort(key=lambda o: (self._val(o), sum(o)), reverse=True)
        return offers

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        remaining = self.max_rounds - self.turn

        # if partner made an offer, evaluate it
        if o is not None:
            their_offer_val = self._val(o)
            # dynamic acceptance threshold, starts high and decreases each turn
            if self.max_rounds > 1:
                progress = (self.turn - 1) / (self.max_rounds - 1)
            else:
                progress = 1.0
            threshold = 0.9 - 0.4 * progress  # from 90% down to 50% of total
            # if it's our very last move (we are second), accept almost anything > 0
            if self.me == 1 and remaining == 0:
                threshold = 0.05
            if self.total == 0 or their_offer_val >= self.total * threshold:
                return None  # accept

        # build a counter-offer
        # proposal target lowers over time to become more conceding
        progress = (self.turn - 1) / max(1, self.max_rounds - 1)
        target = self.total * (0.75 - 0.35 * progress)  # from 75% down to ~40% of total

        # pick the best offer meeting the target; otherwise the best available
        chosen = self.offers[0]
        for off in self.offers:
            if self._val(off) >= target:
                chosen = off
                break

        return chosen