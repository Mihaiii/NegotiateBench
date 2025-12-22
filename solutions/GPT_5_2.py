from __future__ import annotations

from typing import List, Optional


class Agent:
    """
    Haggling agent with:
      - time-dependent concession schedule (acceptance + proposal targets)
      - lightweight opponent preference inference from what they tend to keep
      - bounded knapsack DP to propose a high-value (to us) bundle that should be acceptable (to them)
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = int(me)
        self.counts = list(counts)
        self.values = list(values)
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total_turns = max(1, self.max_rounds * 2)
        self.calls = 0  # number of times offer() has been called on us

        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # Opponent inference: average fraction they keep per item type
        self._opp_offer_count = 0
        self._opp_keep_frac_sum = [0.0] * self.n
        self._last_opp_offer: Optional[List[int]] = None

    # --- public API (framework expects offer; some variants expect make_offer) ---

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        return self._act(o)

    def make_offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        return self._act(o)

    # --- core logic ---

    def _act(self, o: Optional[List[int]]) -> Optional[List[int]]:
        global_turn = 2 * self.calls + self.me
        self.calls += 1
        p = 0.0 if self.total_turns <= 1 else (global_turn / (self.total_turns - 1))

        # If we literally value nothing, any outcome is the same for us (0).
        if self.total <= 0:
            if o is None:
                return [0] * self.n
            return None  # accept immediately

        if o is not None:
            o = self._sanitize_offer(o)
            self._observe_opponent_offer(o)

            # Last chance (if we are the last speaker): accept any valid offer (>=0 for us).
            if global_turn >= self.total_turns - 1:
                return None

            their_offer_value = self._value(o)
            min_accept = self._min_accept_value(p, global_turn)

            # If their offer meets our acceptance threshold, accept.
            if their_offer_value >= min_accept:
                return None

        # Otherwise, craft a counter-offer.
        opp_vals = self._estimate_opponent_values()
        my_target = self._min_accept_value(p, global_turn)  # we'd like to get at least this
        opp_required = self._opponent_required_value(p, o, opp_vals)

        proposal = self._best_offer_given_opp_requirement(opp_vals, opp_required, my_target)

        # If we received an offer and our planned proposal is not better for us, accept instead.
        if o is not None:
            if self._value(o) >= self._value(proposal):
                return None

        return proposal

    # --- thresholds / schedules ---

    def _min_accept_value(self, p: float, global_turn: int) -> int:
        """
        Our acceptance threshold decreases over time.
        - early: ~0.75 * total
        - late:  ~0.45 * total (except final turn handled separately)
        """
        # Basic linear concession: 0.75 -> 0.50
        thr = (0.75 - 0.25 * p) * self.total
        # Extra concession near the end to avoid no-deal
        if p >= 0.85:
            thr = min(thr, 0.45 * self.total)
        # Clamp
        thr = max(0.0, min(float(self.total), thr))
        return int(round(thr))

    def _opponent_required_value(self, p: float, last_offer: Optional[List[int]], opp_vals: List[float]) -> float:
        """
        How much value (estimated) we try to leave for the opponent in OUR proposal.
        We start demanding more (leave them less), and concede over time.
        """
        # Start leaving them about 0.20*total, move toward about 0.50*total
        base = (0.20 + 0.30 * p) * self.total

        # If opponent's last offer seems very "tough" for them (they keep a lot by our estimate),
        # increase what we leave to improve acceptance odds.
        if last_offer is not None:
            opp_total = self.total  # by problem statement, totals match
            opp_get_in_their_offer = self._opp_value_of_their_share(last_offer, opp_vals)
            # If they were demanding a lot, respond by being a bit more generous.
            if opp_get_in_their_offer >= 0.65 * opp_total:
                base = max(base, 0.35 * self.total)

        # Never target leaving them more than 0.55*total (we still want a decent deal)
        return max(0.0, min(0.55 * self.total, base))

    # --- opponent modeling ---

    def _observe_opponent_offer(self, o: List[int]) -> None:
        self._last_opp_offer = o
        self._opp_offer_count += 1
        for i, (ci, oi) in enumerate(zip(self.counts, o)):
            if ci <= 0:
                continue
            keep = ci - oi
            keep_frac = keep / ci
            self._opp_keep_frac_sum[i] += keep_frac

    def _estimate_opponent_values(self) -> List[float]:
        """
        Estimate opponent per-item values from what they tend to keep.
        Normalize so that sum(count[i]*opp_value[i]) == self.total.
        """
        # If no data, use uniform (opponent values all types equally per item).
        if self._opp_offer_count <= 0:
            weights = [1.0] * self.n
        else:
            weights = []
            for i, ci in enumerate(self.counts):
                if ci <= 0:
                    weights.append(0.0)
                    continue
                avg_keep = self._opp_keep_frac_sum[i] / self._opp_offer_count
                # Weight: baseline + emphasis for being kept
                w = 1.0 + 2.5 * avg_keep
                # If they *always* keep almost all, bump further
                if avg_keep >= 0.85:
                    w += 1.0
                weights.append(w)

        denom = sum(w * c for w, c in zip(weights, self.counts))
        if denom <= 0:
            # Fallback: all zero (shouldn't happen with positive counts), but be safe.
            return [0.0] * self.n

        scale = self.total / denom
        return [w * scale for w in weights]

    # --- proposal optimization ---

    def _best_offer_given_opp_requirement(
        self, opp_vals: List[float], opp_required: float, my_target: int
    ) -> List[int]:
        """
        Compute an offer (bundle to us) that:
          - maximizes our value
          - while leaving opponent at least opp_required (estimated)
        Uses bounded knapsack on opponent-loss budget.
        """
        # Opponent estimated total is the same as ours by problem statement.
        opp_total = float(self.total)
        budget_value = max(0.0, opp_total - opp_required)  # how much opp-value we can take from them

        # Choose scaling so DP budget stays reasonable.
        target_budget = 4000
        scale = max(1, int(target_budget / max(1, self.total)))
        w_int = [max(0, int(round(v * scale))) for v in opp_vals]
        budget = int(round(budget_value * scale))

        # Items with zero opponent weight can be taken "for free" wrt acceptance.
        base = [0] * self.n
        pos_idx = []
        for i in range(self.n):
            if self.counts[i] <= 0:
                continue
            if w_int[i] == 0:
                # Take all if we value it; otherwise, leave it (either is fine).
                base[i] = self.counts[i] if self.values[i] > 0 else 0
            else:
                pos_idx.append(i)

        if not pos_idx or budget <= 0:
            # No meaningful constrained optimization possible; return a simple concessionary split.
            # Start from base, then (if needed) add a bit of high-value stuff without regard to opp.
            offer = base[:]
            # Ensure within bounds
            for i in range(self.n):
                offer[i] = max(0, min(self.counts[i], offer[i]))
            # If we don't meet our own target, try to add our highest-value items.
            if self._value(offer) < my_target:
                for i in sorted(range(self.n), key=lambda k: self.values[k], reverse=True):
                    if self.values[i] <= 0:
                        continue
                    offer[i] = self.counts[i]
                    if self._value(offer) >= my_target:
                        break
            return offer

        # DP: dp[b] = best our value achievable with opp-loss exactly b (or <=b tracked by max).
        # We'll compute best for each b and store choices to reconstruct.
        B = max(0, budget)
        dp_prev = [-10**18] * (B + 1)
        dp_prev[0] = 0

        # choices[t][b] = how many units of pos_idx[t] we take at budget b
        choices: List[List[int]] = [[0] * (B + 1) for _ in range(len(pos_idx))]

        for t, i in enumerate(pos_idx):
            ci = self.counts[i]
            wi = w_int[i]
            vi = self.values[i]

            dp_cur = [-10**18] * (B + 1)
            choice_row = choices[t]

            # For each budget b, try x units.
            for b in range(B + 1):
                best_val = -10**18
                best_x = 0
                # Try x=0..ci, but only feasible if b >= wi*x
                # Iterate x and read dp_prev[b-wi*x]
                if wi == 0:
                    # Shouldn't happen (filtered), but keep safe.
                    x_best = ci if vi > 0 else 0
                    best_val = dp_prev[b] + vi * x_best
                    best_x = x_best
                else:
                    max_x = min(ci, b // wi)
                    # Small counts expected; brute force within count is fine.
                    for x in range(max_x + 1):
                        prev = dp_prev[b - wi * x]
                        if prev <= -10**17:
                            continue
                        cand = prev + vi * x
                        if cand > best_val:
                            best_val = cand
                            best_x = x

                dp_cur[b] = best_val
                choice_row[b] = best_x

            dp_prev = dp_cur

        # Pick the best dp value for any b <= B.
        best_b = 0
        best_my = -10**18
        for b in range(B + 1):
            if dp_prev[b] > best_my:
                best_my = dp_prev[b]
                best_b = b

        # Reconstruct offer.
        offer = base[:]
        b = best_b
        for t in range(len(pos_idx) - 1, -1, -1):
            i = pos_idx[t]
            x = choices[t][b]
            offer[i] = x
            b -= w_int[i] * x
            if b < 0:
                b = 0

        # If we ended up far below our target (due to too-high opp_required),
        # relax slightly by reducing opp_required effect: greedily add our high-value items
        # (still keep within counts).
        if self._value(offer) < my_target:
            for i in sorted(range(self.n), key=lambda k: self.values[k], reverse=True):
                if self.values[i] <= 0:
                    continue
                offer[i] = self.counts[i]
                if self._value(offer) >= my_target:
                    break

        # Always valid bounds.
        for i in range(self.n):
            offer[i] = max(0, min(self.counts[i], int(offer[i])))

        return offer

    # --- utilities ---

    def _sanitize_offer(self, o: List[int]) -> List[int]:
        if not isinstance(o, list) or len(o) != self.n:
            # Invalid input from framework/opponent shouldn't happen; treat as worst for inference.
            return [0] * self.n
        out = []
        for i, (x, c) in enumerate(zip(o, self.counts)):
            try:
                xi = int(x)
            except Exception:
                xi = 0
            out.append(max(0, min(c, xi)))
        return out

    def _value(self, o: List[int]) -> int:
        return sum(v * x for v, x in zip(self.values, o))

    def _opp_value_of_their_share(self, o_to_us: List[int], opp_vals: List[float]) -> float:
        # Opponent gets remaining items: counts - o_to_us
        return sum(ov * (c - x) for ov, c, x in zip(opp_vals, self.counts, o_to_us))