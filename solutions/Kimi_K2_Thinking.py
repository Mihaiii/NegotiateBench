from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_offers = max_rounds * 2
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        self.opponent_offer_history: List[List[int]] = []
        self.turn_counter = 0
        # Tunable parameters
        self.start_target_frac = 0.7  # start by aiming for 70 % of our total value

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn_counter += 1
        progress = self.turn_counter / self.total_offers if self.total_offers > 0 else 0.0

        # Record opponent's last proposal (what they would give us)
        if o is not None:
            self.opponent_offer_history.append(o)

        # ---------- Compute our current targets ----------
        # Desired value for ourselves (declines linearly from start_target_frac to 0)
        target_us = int(self.total_value * self.start_target_frac * (1 - progress))
        if target_us < 0:
            target_us = 0

        # Minimal value we guess the opponent will accept (grows linearly from 0 to total)
        target_opp = int(self.total_value * progress)
        if target_opp < 0:
            target_opp = 0

        # ---------- Estimate opponent's per‑type valuation ----------
        n_hist = len(self.opponent_offer_history)

        # Laplace smoothing: prior of one “give” and one “no‑give”
        avg_give = []
        for i in range(self.n):
            total_offered_i = sum(off[i] for off in self.opponent_offer_history)
            # (total_offered_i + 1) / (n_hist + 2)
            avg = (total_offered_i + 1) / (n_hist + 2) if self.total_value > 0 else 0.5
            avg_give.append(avg)

        # weight_i = 1 - avg_give_i (higher weight → opponent cares more about the item)
        weight = [1 - avg_give[i] for i in range(self.n)]

        # Scale weights so that the opponent’s total estimated value equals our total value
        denom = sum(weight[i] * self.counts[i] for i in range(self.n))
        scaling = self.total_value / denom if denom > 0 else 0.0
        opp_values = [int(round(weight[i] * scaling)) for i in range(self.n)]

        # ---------- Acceptance decision ----------
        if o is not None:
            # Value we would obtain by accepting the opponent's proposal
            offered_value = sum(o[i] * self.values[i] for i in range(self.n))

            # Our acceptance threshold softens as the deadline approaches
            accept_factor = 1.0 - progress * 0.5  # from 1 down to 0.5
            min_accept = int(target_us * accept_factor)
            if min_accept < 0:
                min_accept = 0

            if offered_value >= min_accept:
                return None  # accept

            # If we are the last mover on the final turn, accept anything rather than get zero
            if self.me == 1 and self.turn_counter == self.total_offers:
                return None

        # ---------- Build our counter‑offer ----------
        allocation = self._compute_offer(opp_values, target_opp)
        return allocation

    def _compute_offer(self, opp_values: List[int], target_opp: int) -> List[int]:
        """
        Solve a bi‑criteria knapsack: maximize our value subject to the opponent receiving
        at least target_opp.  The problem is tiny (≤10 types, ≤10 copies each),
        so a DP over opponent value is feasible.
        """
        n = self.n
        counts = self.counts
        values = self.values

        # dp[i][o] = maximum our value reachable after processing the first i types
        # and achieving exactly opponent value o.
        dp = [dict() for _ in range(n + 1)]
        pred = [dict() for _ in range(n + 1)]

        dp[0][0] = 0
        pred[0][0] = None

        for i in range(n):
            dp[i + 1] = {}
            pred[i + 1] = {}
            c = counts[i]
            v = values[i]
            ov = opp_values[i]

            # Reduce the branch factor for types that are worthless to one side
            if ov == 0:
                # opponent does not value this type – keep everything for ourselves
                ks = [c]
            elif v == 0:
                # we do not value this type – give everything to opponent
                ks = [0]
            else:
                ks = range(c + 1)

            for o_prev, u_prev in dp[i].items():
                for k in ks:
                    new_o = o_prev + (c - k) * ov
                    new_u = u_prev + k * v
                    # keep the best (max our value) for this opponent value
                    if new_o not in dp[i + 1] or new_u > dp[i + 1][new_o]:
                        dp[i + 1][new_o] = new_u
                        pred[i + 1][new_o] = (o_prev, k)

        # Select the best final state: opponent value >= target_opp and our value maximal
        best_o = None
        best_u = -1
        for o_final, u_final in dp[n].items():
            if o_final >= target_opp and u_final > best_u:
                best_o = o_final
                best_u = u_final

        # If no state reaches the opponent's target, fall back to the state with maximum our value
        if best_o is None:
            best_o, best_u = max(dp[n].items(), key=lambda item: item[1])

        # Reconstruct the allocation that leads to the chosen state
        alloc = [0] * n
        cur_o = best_o
        for i in range(n, 0, -1):
            prev_o, k = pred[i][cur_o]
            alloc[i - 1] = k
            cur_o = prev_o

        return alloc