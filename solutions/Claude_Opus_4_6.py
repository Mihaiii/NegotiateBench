class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.opponent_offers = []
        self.my_offers = []
        self.turn = 0
        
        # Precompute all possible splits and their values
        self.all_splits = self._enumerate_splits()
        
    def _my_value(self, offer):
        return sum(self.values[i] * offer[i] for i in range(self.n))
    
    def _enumerate_splits(self):
        def generate(idx):
            if idx == self.n:
                yield []
                return
            for k in range(self.counts[idx] + 1):
                for rest in generate(idx + 1):
                    yield [k] + rest
        result = list(generate(0))
        # Limit if too many splits
        if len(result) > 50000:
            # Filter to only reasonably good ones
            result = [s for s in result if self._my_value(s) >= self.total * 0.3]
        return result
    
    def _estimate_opponent_values(self):
        """Estimate per-unit opponent values from their offers."""
        if not self.opponent_offers:
            return None
        
        # Track how much opponent keeps of each item type across offers
        # Items they consistently keep more of are more valuable to them
        keep_scores = [0.0] * self.n
        for offer in self.opponent_offers:
            for i in range(self.n):
                if self.counts[i] > 0:
                    kept = self.counts[i] - offer[i]
                    keep_scores[i] += kept / self.counts[i]
        
        total_score = sum(keep_scores)
        if total_score == 0:
            return None
        
        # Per-unit estimated value
        est = []
        for i in range(self.n):
            if self.counts[i] > 0:
                est.append(keep_scores[i] / total_score * self.total / self.counts[i])
            else:
                est.append(0)
        return est
    
    def _opp_value(self, my_split, opp_vals):
        """Estimate opponent's value for their share given my split."""
        return sum(opp_vals[i] * (self.counts[i] - my_split[i]) for i in range(self.n))
    
    def _score_split(self, split, opp_vals, my_target_frac):
        """Score a split considering both my value and estimated opponent value."""
        mv = self._my_value(split)
        if opp_vals:
            ov = self._opp_value(split, opp_vals)
        else:
            # Without info, prefer giving away zero-value items
            ov = sum((self.counts[i] - split[i]) for i in range(self.n) if self.values[i] == 0)
        return mv, ov

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        
        if o is not None:
            self.opponent_offers.append(o[:])
        
        progress = self.turn / (self.max_rounds * 2)  # 0 to ~1
        is_last_turn = self.turn >= self.max_rounds * 2 if self.me == 1 else self.turn >= self.max_rounds * 2 - 1
        rounds_left = self.max_rounds - (self.turn + 1) // 2
        
        opp_vals = self._estimate_opponent_values()
        
        # Determine acceptance threshold
        # Start high, decrease over time
        if is_last_turn or rounds_left <= 0:
            accept_threshold = max(1, self.total * 0.1)
        elif rounds_left <= 1:
            accept_threshold = max(1, self.total * 0.2)
        elif rounds_left <= 2:
            accept_threshold = max(1, self.total * 0.25)
        else:
            # Gradually lower from ~65% to ~35%
            accept_threshold = self.total * max(0.30, 0.65 - 0.35 * progress)
        
        # Check if we should accept the current offer
        if o is not None:
            my_val = self._my_value(o)
            if my_val >= accept_threshold:
                # Also check: is this likely better than what we'd get by counter-offering?
                # On last rounds, definitely accept
                if my_val >= self.total * 0.5 or rounds_left <= 1:
                    return None
                # Accept if it's reasonably good
                if my_val >= self.total * 0.4:
                    return None
                # Check if opponent is conceding over time
                if len(self.opponent_offers) >= 2:
                    prev_val = self._my_value(self.opponent_offers[-2])
                    if my_val >= prev_val and my_val >= accept_threshold:
                        return None
                if my_val >= accept_threshold:
                    return None
        
        # Generate our offer
        # Target decreases over time to make concessions
        if rounds_left <= 0:
            target_frac = 0.35
        elif rounds_left <= 1:
            target_frac = 0.40
        elif rounds_left <= 2:
            target_frac = 0.45
        else:
            target_frac = max(0.40, 0.75 - 0.35 * progress)
        
        my_target = self.total * target_frac
        
        # Score all splits
        candidates = []
        for split in self.all_splits:
            mv = self._my_value(split)
            if mv < my_target * 0.8:
                continue
            if opp_vals:
                ov = self._opp_value(split, opp_vals)
            else:
                # Give away zero-value items
                ov = sum((self.counts[i] - split[i]) * 1.0 for i in range(self.n) if self.values[i] == 0)
            
            # Prefer splits where I get close to target and opponent gets a lot
            # Nash-bargaining-like: maximize product (or weighted sum)
            my_surplus = mv
            opp_surplus = ov
            
            # Combined score: my value + weight * opponent value
            # Weight increases over time (more cooperative as deadline approaches)
            opp_weight = 0.3 + 0.5 * progress
            score = mv + opp_weight * opp_surplus
            
            candidates.append((score, mv, ov, split))
        
        if not candidates:
            # Fallback: take everything valuable
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        # Sort by combined score, break ties by my value
        candidates.sort(key=lambda x: (-x[0], -x[1]))
        
        # Pick the best candidate that gives us at least our target
        best = None
        for score, mv, ov, split in candidates:
            if mv >= my_target * 0.85:
                best = split
                break
        
        if best is None:
            best = candidates[0][3]
        
        # Don't repeat the exact same offer too many times - make a small concession
        if len(self.my_offers) >= 3:
            last_offers = self.my_offers[-3:]
            if all(off == best for off in last_offers):
                # Find next best alternative that's slightly different
                for score, mv, ov, split in candidates:
                    if split != best and mv >= my_target * 0.75:
                        best = split
                        break
        
        self.my_offers.append(best[:])
        return best