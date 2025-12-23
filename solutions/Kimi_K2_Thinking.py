import math
from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        # total number of turns (two per round)
        self.total_turns = max_rounds * 2
        self.n = len(counts)

        # total value of all items for us (used for normalization)
        self.total_value = sum(c * v for c, v in zip(counts, values))

        # opponent modeling: history of offers we have received
        self.opp_offers = []

        # initialise opponent value estimates uniformly
        total_items = sum(counts)
        uniform_val = self.total_value / total_items if total_items > 0 else 0
        self.opp_weights = [uniform_val] * self.n

        # state tracking
        self.turn = 0
        self.best_seen = 0

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        pressure = self.turn / self.total_turns if self.total_turns > 0 else 0.0

        # process the opponent's offer (what we would get if we accept)
        if o is not None:
            self.opp_offers.append(o)
            self._update_opponent_weights()

            our_val = sum(o[i] * self.values[i] for i in range(self.n))
            self.best_seen = max(self.best_seen, our_val)

            if self._should_accept(o, pressure):
                return None

        # final turn: last mover must accept or the negotiation ends with zero payoff
        if self.turn == self.total_turns and self.me == 1:
            return None

        # propose a new split for ourselves
        return self._make_offer(pressure)

    def _update_opponent_weights(self) -> None:
        """Exponential smoothing of opponent's average keep‑fraction per item type."""
        if not self.opp_offers:
            return

        n = len(self.opp_offers)
        alpha = min(0.25, 1.0 / math.sqrt(n + 1))

        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            # fraction of this item type the opponent has kept in past offers
            total_kept = sum(self.counts[i] - offer[i] for offer in self.opp_offers)
            avg_keep_frac = total_kept / (n * self.counts[i])
            # smooth the estimate
            self.opp_weights[i] = (1 - alpha) * self.opp_weights[i] + alpha * avg_keep_frac

        # re‑normalise so the weighted sum equals the total (known) aggregate value
        weighted_sum = sum(self.opp_weights[i] * self.counts[i] for i in range(self.n))
        if weighted_sum > 0:
            scale = self.total_value / weighted_sum
            self.opp_weights = [w * scale for w in self.opp_weights]

    def _should_accept(self, o: List[int], pressure: float) -> bool:
        """Accept if the offer is good enough, accounting for time pressure."""
        our_val = sum(o[i] * self.values[i] for i in range(self.n))

        if our_val == 0:
            return False  # never accept a worthless split unless forced

        # approximate opponent's valuation of the items they would keep
        opp_keeps = [self.counts[i] - o[i] for i in range(self.n)]
        opp_val = sum(opp_keeps[i] * self.opp_weights[i] for i in range(self.n))

        # "generosity" – how much of their own value is the opponent giving up?
        generosity = 0.0
        for i in range(self.n):
            if self.opp_weights[i] > 0:
                generosity += (o[i] / max(self.counts[i], 1)) * self.opp_weights[i]

        # dynamic threshold: start at ~45 % of our total value, drop as deadline nears
        base_threshold = self.total_value * (0.45 * (1 - 0.7 * pressure))
        # generous offers lower the bar further
        generosity_discount = 0.15 * min(generosity / max(self.total_value, 1), 1.0)
        min_needed = int(base_threshold * (1 - generosity_discount))

        # also accept anything that beats our previous best by a margin
        if our_val > self.best_seen * 1.15:
            return True

        return our_val >= min_needed

    def _make_offer(self, pressure: float) -> List[int]:
        """Propose a split that aims for a target value, favouring items we value
        relatively more than the opponent."""
        # target value declines from 65 % to 30 % as the deadline approaches
        target_us = int(self.total_value * (0.65 - 0.35 * pressure))

        alloc = [0] * self.n
        cur_val = 0

        # compute value‑density ratio for each item type
        ratios = []
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            if self.opp_weights[i] <= 0.1:
                ratio = float('inf') if self.values[i] > 0 else 0.0
            else:
                ratio = self.values[i] / self.opp_weights[i]
            ratios.append((i, ratio, self.values[i], self.counts[i]))

        # allocate from the most favourable ratio downwards
        ratios.sort(key=lambda x: x[1], reverse=True)
        for idx, _, val, cnt in ratios:
            if cur_val >= target_us or val == 0:
                break
            # how many of this item do we need to get close to the target?
            need = (target_us - cur_val) // val if val > 0 else cnt
            take = min(cnt, max(0, need))
            alloc[idx] = take
            cur_val += take * val

        return alloc