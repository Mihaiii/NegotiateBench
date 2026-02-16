class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.total_turns = max_rounds * 2
        self.turn = 0
        self.opponent_offers = []
        self.my_offers = []
        self.best_received_val = 0
        self.best_received = None

        # Enumerate all splits if feasible
        space_size = 1
        for c in counts:
            space_size *= (c + 1)
            if space_size > 500000:
                break

        self.all_splits = []
        if space_size <= 500000:
            self._enumerate(0, [])

        # Generate opponent hypotheses
        self.opp_hypotheses = self._generate_hypotheses()
        self.hyp_weights = [1.0] * len(self.opp_hypotheses)

        # Precompute Pareto frontier for each hypothesis
        self.concession_schedule = []
        self.offer_history_set = set()

    def _enumerate(self, idx, current):
        if idx == self.n:
            self.all_splits.append(tuple(current))
            return
        for k in range(self.counts[idx] + 1):
            current.append(k)
            self._enumerate(idx + 1, current)
            current.pop()

    def _my_value(self, split):
        return sum(self.values[i] * split[i] for i in range(self.n))

    def _opp_value_remainder(self, my_split, opp_vals):
        return sum(opp_vals[i] * (self.counts[i] - my_split[i]) for i in range(self.n))

    def _generate_hypotheses(self):
        """Generate diverse plausible opponent valuations summing to self.total."""
        import random
        rng = random.Random(42)
        hypotheses = []
        seen = set()

        non_zero_indices = [i for i in range(self.n) if self.counts[i] > 0]
        if not non_zero_indices or self.total == 0:
            return [[0] * self.n]

        # Systematic generation: try all ways to assign integer per-unit values
        # Use recursive distribution of total across item types
        def distribute(remaining, idx, current):
            if len(hypotheses) > 300:
                return
            if idx == len(non_zero_indices):
                if remaining == 0:
                    h = [0] * self.n
                    for j, ii in enumerate(non_zero_indices):
                        h[ii] = current[j]
                    key = tuple(h)
                    if key not in seen:
                        seen.add(key)
                        hypotheses.append(h)
                return
            i = non_zero_indices[idx]
            c = self.counts[i]
            max_per = remaining // c
            for v in range(max_per + 1):
                current.append(v)
                distribute(remaining - v * c, idx + 1, current)
                current.pop()

        if len(non_zero_indices) <= 6 and self.total <= 50:
            distribute(self.total, 0, [])

        # If too few or too many, supplement with random
        attempts = 0
        while len(hypotheses) < 200 and attempts < 2000:
            attempts += 1
            vals = [0] * self.n
            remaining = self.total
            indices = non_zero_indices[:]
            rng.shuffle(indices)

            for j, i in enumerate(indices):
                c = self.counts[i]
                if j == len(indices) - 1:
                    if remaining % c == 0:
                        vals[i] = remaining // c
                        remaining = 0
                    else:
                        break
                else:
                    max_per = remaining // c
                    vals[i] = rng.randint(0, max_per)
                    remaining -= vals[i] * c

            if remaining == 0:
                key = tuple(vals)
                if key not in seen:
                    seen.add(key)
                    hypotheses.append(vals)

        if not hypotheses:
            # Fallback
            hypotheses.append([0] * self.n)

        return hypotheses

    def _update_weights(self):
        """Bayesian update of hypothesis weights based on opponent offers."""
        if not self.opponent_offers:
            return

        for h_idx, opp_vals in enumerate(self.opp_hypotheses):
            opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
            if opp_total == 0:
                self.hyp_weights[h_idx] = 1e-6
                continue

            log_likelihood = 0.0
            for offer in self.opponent_offers:
                # offer = what opponent gives to ME
                # opponent keeps counts[i] - offer[i]
                opp_keeps = sum(opp_vals[i] * (self.counts[i] - offer[i]) for i in range(self.n))
                frac = opp_keeps / opp_total
                # Rational opponent keeps high value for themselves
                # Use exponential model: P(offer | values) ~ exp(beta * frac)
                beta = 4.0
                import math
                log_likelihood += beta * frac
            
            import math
            self.hyp_weights[h_idx] = math.exp(min(50, log_likelihood))

        # Normalize
        total_w = sum(self.hyp_weights)
        if total_w > 0:
            self.hyp_weights = [w / total_w for w in self.hyp_weights]
        else:
            self.hyp_weights = [1.0 / len(self.opp_hypotheses)] * len(self.opp_hypotheses)

    def _expected_opp_values(self):
        """Weighted average of opponent values."""
        self._update_weights()
        expected = [0.0] * self.n
        for h_idx, opp_vals in enumerate(self.opp_hypotheses):
            w = self.hyp_weights[h_idx]
            for i in range(self.n):
                expected[i] += w * opp_vals[i]
        return expected

    def _compute_pareto_frontier(self, opp_vals):
        """Find Pareto-optimal splits (no split dominates another in both my and opp value)."""
        if not self.all_splits:
            return []

        scored = []
        for s in self.all_splits:
            mv = self._my_value(s)
            ov = self._opp_value_remainder(s, opp_vals)
            scored.append((mv, ov, s))

        # Sort by my value descending
        scored.sort(key=lambda x: (-x[0], -x[1]))

        # Extract Pareto frontier
        frontier = []
        max_ov = -1
        for mv, ov, s in scored:
            if ov > max_ov:
                frontier.append((mv, ov, s))
                max_ov = ov

        return frontier

    def _generate_candidates_large(self, opp_vals, min_my_val):
        """For large spaces, generate candidates heuristically."""
        import random
        rng = random.Random(self.turn * 7 + 99)

        candidates = []
        seen = set()

        # Compute efficiency ratios
        ratios = []
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            my_per = self.values[i]
            op_per = opp_vals[i]
            # Ratio of my value to opponent value - higher means I should take it
            ratio = (my_per + 0.01) / (op_per + 0.01)
            ratios.append((ratio, i))
        ratios.sort(reverse=True)

        # Strategy: greedily take items with best ratio, leave rest for opponent
        for trial in range(1000):
            split = [0] * self.n

            if trial < 5:
                # Greedy with different thresholds
                thresholds = [2.0, 1.5, 1.0, 0.7, 0.5]
                thresh = thresholds[trial]
                for ratio, i in ratios:
                    if ratio >= thresh:
                        split[i] = self.counts[i]
                    elif ratio >= thresh * 0.5:
                        split[i] = self.counts[i] // 2
            elif trial < 50:
                # Systematic: take top-k item types fully
                k = trial - 5
                for j, (ratio, i) in enumerate(ratios):
                    if j < k % (len(ratios) + 1):
                        split[i] = self.counts[i]
                    else:
                        # Partial amounts
                        split[i] = rng.randint(0, self.counts[i])
            else:
                # Random with bias toward efficient items
                for ratio, i in ratios:
                    p = min(0.95, ratio / (ratio + 1))
                    expected = int(self.counts[i] * p)
                    split[i] = min(self.counts[i], max(0,
                        expected + rng.randint(-1, 1)))

            key = tuple(split)
            if key in seen:
                continue
            seen.add(key)

            mv = self._my_value(split)
            ov = self._opp_value_remainder(split, opp_vals)
            candidates.append((mv, ov, list(split)))

        # Add special splits
        for special in [
            list(self.counts),  # take all
            [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)],  # take valued
            [0] * self.n,  # take nothing
        ]:
            key = tuple(special)
            if key not in seen:
                seen.add(key)
                mv = self._my_value(special)
                ov = self._opp_value_remainder(special, opp_vals)
                candidates.append((mv, ov, special))

        return candidates

    def _pick_offer(self, progress):
        """Select the best offer based on current state."""
        if self.total == 0:
            return [0] * self.n

        opp_vals = self._expected_opp_values()
        turns_left = self.total_turns - self.turn

        # Determine target my_value based on concession curve
        # Start demanding ~90% of total, concede toward ~35%
        if self.total_turns <= 4:
            start = 0.85
            end = 0.25
        elif self.total_turns <= 10:
            start = 0.88
            end = 0.20
        else:
            start = 0.90
            end = 0.15

        # Use Boulware-like concession: slow at first, faster near end
        # progress^beta where beta > 1 = Boulware
        beta = 3.0
        concession = progress ** beta
        target_frac = start - (start - end) * concession
        target_val = self.total * target_frac

        # Get candidates
        if self.all_splits:
            frontier = self._compute_pareto_frontier(opp_vals)
            candidates = [(mv, ov, list(s)) for mv, ov, s in frontier]
            # Also add non-frontier splits for variety
            for s in self.all_splits:
                mv = self._my_value(s)
                ov = self._opp_value_remainder(s, opp_vals)
                candidates.append((mv, ov, list(s)))
        else:
            candidates = self._generate_candidates_large(opp_vals, target_val * 0.5)

        if not candidates:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]

        # Filter: must give me at least target_val (with some flexibility)
        min_acceptable = max(1, target_val * 0.9)

        # Score candidates
        # We want: high my_value (at least target) + high opp_value (so they accept)
        best_score = -float('inf')
        best_split = None
        best_candidates = []

        for mv, ov, s in candidates:
            if mv < min_acceptable:
                continue

            # Nash product variant: maximize my_value * opp_value
            # But weight my_value more early, opponent value more late
            if ov < 0:
                ov = 0

            # Score: prioritize offers opponent is likely to accept
            # while maintaining our minimum
            opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
            opp_frac = ov / max(1, opp_total)

            # The opponent needs to get enough to want to accept
            # Estimate: they need at least (1-progress^2) * their total in early rounds
            # and less later
            opp_min_frac = max(0.1, 0.5 * (1 - progress))

            score = mv  # Base: maximize my value
            # Bonus for giving opponent enough to accept
            if opp_frac >= 0.3:
                score += mv * 0.3  # Feasibility bonus
            if opp_frac >= 0.5:
                score += mv * 0.2

            # Nash component (grows with progress)
            nash_weight = 0.3 + 0.7 * progress
            if mv > 0 and ov > 0:
                import math
                nash = math.sqrt(mv * ov)
                score += nash_weight * nash

            best_candidates.append((score, mv, ov, s))

        if not best_candidates:
            # Lower threshold
            min_acceptable = max(1, target_val * 0.5)
            for mv, ov, s in candidates:
                if mv < min_acceptable:
                    continue
                score = mv + 0.5 * max(0, ov)
                best_candidates.append((score, mv, ov, s))

        if not best_candidates:
            # Take highest value for me
            candidates.sort(key=lambda x: -x[0])
            return candidates[0][2]

        best_candidates.sort(key=lambda x: -x[0])

        # Pick best that we haven't offered too many times
        offer_counts = {}
        for prev in self.my_offers:
            key = tuple(prev)
            offer_counts[key] = offer_counts.get(key, 0) + 1

        for score, mv, ov, s in best_candidates:
            key = tuple(s)
            if offer_counts.get(key, 0) < 3:
                return s

        # If all top candidates exhausted, pick the best anyway
        return best_candidates[0][3]

    def _should_accept(self, o, progress):
        """Decide whether to accept the opponent's offer."""
        my_val = self._my_value(o)
        turns_left = self.total_turns - self.turn

        # Always accept full value
        if my_val >= self.total:
            return True

        # Never accept 0 if we have positive total
        if my_val <= 0 and self.total > 0:
            return False

        my_frac = my_val / max(1, self.total)

        # If this is the last turn where we can accept, be generous
        # (if we reject, we need to make an offer that opponent accepts on their last turn,
        #  or we get nothing)
        if turns_left <= 0:
            # This IS the last action. Accept anything > 0.
            return my_val >= 1

        if turns_left <= 1:
            # After this, opponent gets one more chance or it's over
            # Accept if reasonable
            return my_val >= max(1, self.total * 0.05)

        if turns_left <= 2:
            return my_val >= max(1, self.total * 0.10)

        if turns_left <= 4:
            return my_val >= max(1, self.total * 0.15)

        # Compute what we'd target with our next offer
        beta = 3.0
        if self.total_turns <= 4:
            start, end = 0.85, 0.25
        elif self.total_turns <= 10:
            start, end = 0.88, 0.20
        else:
            start, end = 0.90, 0.15

        # What would next turn's progress be?
        next_progress = self.turn / max(1, self.total_turns - 1)
        concession = next_progress ** beta
        next_target_frac = start - (start - end) * concession
        next_target_val = self.total * next_target_frac

        # Accept if offer >= our next target (we'd be happy to get this)
        if my_val >= next_target_val:
            return True

        # Accept if >= 50%
        if my_frac >= 0.50:
            return True

        # Accept if >= 40% and past early game
        if my_frac >= 0.40 and progress > 0.3:
            return True

        # Accept if >= 30% and past mid game
        if my_frac >= 0.30 and progress > 0.5:
            return True

        # Accept if >= 20% and near end
        if my_frac >= 0.20 and progress > 0.75:
            return True

        # Accept if this is the best offer we've received and we're past halfway
        # and it's at least somewhat reasonable
        if my_val >= self.best_received_val and my_frac >= 0.15 and progress > 0.6:
            return True

        # Accept if opponent is improving offers and we're past midway
        if len(self.opponent_offers) >= 2 and progress > 0.4:
            recent_vals = [self._my_value(x) for x in self.opponent_offers[-3:]]
            if my_val >= max(recent_vals) and my_frac >= 0.20:
                return True

        return False

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        progress = (self.turn - 1) / max(1, self.total_turns - 1)

        if o is not None:
            self.opponent_offers.append(o[:])
            val = self._my_value(o)
            if val > self.best_received_val:
                self.best_received_val = val
                self.best_received = o[:]

            if self._should_accept(o, progress):
                return None

        # Generate counter-offer
        best = self._pick_offer(progress)
        self.my_offers.append(best[:])
        return best