import math
from typing import List

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        self.opponent_offer_history: List[List[int]] = []
        self.turn_counter = 0
        self.total_offers = max_rounds * 2
        # Aim for 50% of total value at the start, decreasing to 0 by the end.
        self.target_us_factor = 0.5

    def offer(self, o: List[int] | None) -> List[int] | None:
        # count this turn
        self.turn_counter += 1
        # progress from 0 (start) to 1 (end)
        progress = self.turn_counter / self.total_offers if self.total_offers > 0 else 0.0
        # value we aim for in this round (linearly decreasing)
        target_us = int(self.total_value * self.target_us_factor * (1 - progress))

        # If we are the last mover on the final turn, accepting any offer is better than a sure zero.
        if self.me == 1 and self.turn_counter == self.total_offers:
            if o is not None:
                return None  # accept

        # ----- acceptance decision -----
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(self.n))
            if offered_value >= target_us:
                return None  # accept the opponent's offer

            # store opponent's offer for later estimation
            self.opponent_offer_history.append(o)

        # ----- estimate opponent's valuations -----
        # default neutral prior (0.5 means ``indifferent'')
        avg_ratio = [0.5] * self.n
        if self.opponent_offer_history:
            for i in range(self.n):
                total_offered = sum(off[i] for off in self.opponent_offer_history)
                avg_ratio[i] = total_offered / len(self.opponent_offer_history) / self.counts[i]

        # weight_i = 1 - avg_ratio (higher means opponent cares more about the item)
        weight = [1 - avg_ratio[i] for i in range(self.n)]

        # scaling factor so that opponent's total estimated value equals our total value
        total_weighted_counts = sum(self.counts[i] * weight[i] for i in range(self.n))
        scaling = self.total_value / total_weighted_counts if total_weighted_counts > 0 else 0.0
        opp_val_per_item = [weight[i] * scaling for i in range(self.n)]

        # ----- build an offer that is good for us and palatable to opponent -----
        eps = 1e-9
        ratio = [self.values[i] / (opp_val_per_item[i] + eps) for i in range(self.n)]

        # sort types by decreasing ratio (we prefer to keep items with high ratio)
        sorted_idx = sorted(range(self.n), key=lambda i: ratio[i], reverse=True)

        our_offer = [0] * self.n
        remaining_target = target_us

        for i in sorted_idx:
            if self.values[i] == 0:
                # we are indifferent; keep none for ourselves
                continue
            if remaining_target <= 0:
                # we already meet our own target
                break
            # how many of this type we need to take (at least one if we still need value)
            need_items = max(1, int(math.ceil(remaining_target / self.values[i])))
            take = min(self.counts[i], need_items)
            our_offer[i] = take
            remaining_target -= take * self.values[i]

        # If we still have a positive remaining_target we simply cannot reach it; we return the best we can do.
        return our_offer