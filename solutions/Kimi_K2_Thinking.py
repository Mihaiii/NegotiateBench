import math
from typing import List

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me                    # 0 if we move first, 1 if second
        self.counts = counts             # list of item counts per type
        self.values = values             # our valuation per item type
        self.max_rounds = max_rounds
        self.n_types = len(counts)
        self.total_items = sum(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_turns = max_rounds * 2
        self.turns_passed = 0

        # Opponent's value estimate: start uniform (same total value)
        if self.total_items > 0:
            self.opp_est = [self.total_value / self.total_items] * self.n_types
        else:
            self.opp_est = [0.0] * self.n_types

    # -------------------------------------------------------------
    # Update opponent value estimate based on their last offer
    def _update_opp_estimate(self, o: List[int]):
        # o[i] = number of items of type i the opponent offered to us
        keep = [self.counts[i] - o[i] for i in range(self.n_types)]
        total_keep = sum(keep)
        if total_keep == 0:
            # No information: opponent gave away everything
            return
        avg_keep_frac = total_keep / self.total_items
        new_est = [0.0] * self.n_types
        for i in range(self.n_types):
            if self.counts[i] == 0:
                new_est[i] = self.opp_est[i]
                continue
            keep_frac_i = keep[i] / self.counts[i]
            # multiplicative factor relative to average
            factor = keep_frac_i / avg_keep_frac
            new_est[i] = self.opp_est[i] * factor

        # renormalise so that sum_i new_est[i] * counts[i] == total_value
        total_est = sum(new_est[i] * self.counts[i] for i in range(self.n_types))
        if total_est > 0:
            scale = self.total_value / total_est
            for i in range(self.n_types):
                new_est[i] *= scale
        self.opp_est = new_est

    # -------------------------------------------------------------
    def _compute_targets(self) -> (float, float, float):
        """Return (target_us, target_opp, capacity) for the current turn."""
        # opponent's minimal share increases linearly from 0 to 0.5 of total value
        opp_share = (self.turns_passed / self.total_turns) * 0.5
        target_opp = self.total_value * opp_share
        target_us = self.total_value - target_opp          # what we would like to obtain
        # capacity in terms of opponent value we are allowed to “spend”
        capacity = target_us
        return target_us, target_opp, capacity

    # -------------------------------------------------------------
    def _solve_allocation(self, capacity: float):
        """
        Solve the knapsack: maximise our profit subject to
        sum_i (opp_est[i] * x[i]) <= capacity.
        Returns (allocation list, profit).
        """
        # Types with zero value to us are given to opponent – they don't affect profit
        alloc = [0] * self.n_types
        profit = 0

        # If total_value is zero, any split is fine; we keep nothing.
        if self.total_value == 0:
            return alloc, profit

        # We'll solve a knapsack on profit (integer) minimizing opponent weight.
        max_profit = self.total_value
        dp = [float('inf')] * (max_profit + 1)
        dp[0] = 0.0

        # predecessor arrays to reconstruct the solution
        prev_piece = [-1] * (max_profit + 1)
        prev_profit = [-1] * (max_profit + 1)

        # Create pieces using binary splitting for each type where we value the item > 0
        pieces = []   # each piece is (type_index, count, profit, weight)
        for i in range(self.n_types):
            if self.values[i] == 0:
                # we will keep none of these (give them to opponent)
                continue
            cnt = self.counts[i]
            val = self.values[i]
            # opponent weight per item of this type
            w_per = self.opp_est[i]
            # decompose cnt into powers of two
            k = 1
            while cnt > 0:
                take = min(k, cnt)
                profit = take * val
                weight = take * w_per
                pieces.append((i, take, profit, weight))
                cnt -= take
                k <<= 1

        # DP over profit
        for idx, (typ, cnt, gain, wgt) in enumerate(pieces):
            for p in range(max_profit - gain, -1, -1):
                if dp[p] + wgt < dp[p + gain]:
                    dp[p + gain] = dp[p] + wgt
                    prev_piece[p + gain] = idx
                    prev_profit[p + gain] = p

        # Find the best profit whose required opponent weight does not exceed capacity
        best_profit = 0
        for p in range(max_profit, -1, -1):
            if dp[p] <= capacity + 1e-9:   # allow tiny tolerance
                best_profit = p
                break

        # Reconstruct the allocation for types that have positive value to us
        for _ in range(self.n_types):
            # placeholder to avoid errors
            pass
        # Actually reconstruct:
        cur = best_profit
        while cur > 0 and prev_piece[cur] != -1:
            idx = prev_piece[cur]
            typ, cnt, gain, wgt = pieces[idx]
            alloc[typ] += cnt
            cur = prev_profit[cur]

        # For items we value zero, we keep none (give them to opponent)
        for i in range(self.n_types):
            if self.values[i] == 0:
                alloc[i] = 0

        # The profit we obtain is exactly best_profit
        return alloc, best_profit

    # -------------------------------------------------------------
    def offer(self, o: List[int] | None) -> List[int] | None:
        # Count this turn
        self.turns_passed += 1

        # Update opponent model if we received an offer
        if o is not None:
            self._update_opp_estimate(o)

        # Determine our current target and the opponent capacity we may consume
        target_us, target_opp, capacity = self._compute_targets()

        # Solve the knapsack to get the best allocation we can achieve under capacity
        allocation, profit = self._solve_allocation(capacity)

        # Acceptance threshold: if we can reach our target, we aim for it;
        # otherwise we settle for the best we can obtain (profit).
        threshold = min(target_us, profit)

        # If we have an offer, decide whether to accept it
        if o is not None:
            # value of the opponent's offer to us
            value_us = sum(self.values[i] * o[i] for i in range(self.n_types))
            if value_us >= threshold - 1e-9:
                return None   # accept

        # Otherwise we make a counter‑offer (the allocation we just computed)
        return allocation