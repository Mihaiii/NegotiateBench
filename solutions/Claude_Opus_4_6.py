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
        
        # Precompute all splits if feasible
        self.all_splits = []
        space_size = 1
        for c in counts:
            space_size *= (c + 1)
            if space_size > 300000:
                break
        
        if space_size <= 300000:
            self._enumerate(0, [])
        
        # Sort splits by my value descending
        self.all_splits.sort(key=lambda s: self._my_value(s), reverse=True)
        
        # Generate all valid opponent value hypotheses
        self.opp_hypotheses = self._generate_opp_hypotheses()
        self.hyp_weights = [1.0] * len(self.opp_hypotheses) if self.opp_hypotheses else []
        
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
    
    def _opp_value_from_my_split(self, my_split, opp_vals):
        return sum(opp_vals[i] * (self.counts[i] - my_split[i]) for i in range(self.n))
    
    def _generate_opp_hypotheses(self):
        """Generate all possible opponent valuations (non-negative integers summing to self.total)."""
        non_zero_count = [i for i in range(self.n) if self.counts[i] > 0]
        if not non_zero_count or self.total == 0:
            return [[0] * self.n]
        
        hypotheses = []
        
        def distribute(remaining, idx, current):
            if len(hypotheses) > 5000:
                return
            if idx == len(non_zero_count):
                if remaining == 0:
                    h = [0] * self.n
                    for j, ii in enumerate(non_zero_count):
                        h[ii] = current[j]
                    hypotheses.append(h)
                return
            i = non_zero_count[idx]
            c = self.counts[i]
            max_per = remaining // c
            for v in range(max_per + 1):
                current.append(v)
                distribute(remaining - v * c, idx + 1, current)
                current.pop()
        
        if len(non_zero_count) <= 8 and self.total <= 50:
            distribute(self.total, 0, [])
        
        if not hypotheses:
            # Generate sampled hypotheses
            import random
            rng = random.Random(42)
            for _ in range(2000):
                h = [0] * self.n
                remaining = self.total
                indices = list(range(self.n))
                rng.shuffle(indices)
                for idx, i in enumerate(indices):
                    if self.counts[i] == 0:
                        continue
                    if idx == len(indices) - 1 or all(self.counts[j] == 0 for j in indices[idx+1:]):
                        if remaining % self.counts[i] == 0:
                            h[i] = remaining // self.counts[i]
                            remaining = 0
                        else:
                            break
                    else:
                        max_v = remaining // self.counts[i]
                        v = rng.randint(0, max_v)
                        h[i] = v
                        remaining -= v * self.counts[i]
                if remaining == 0:
                    hypotheses.append(h)
            
            # Deduplicate
            seen = set()
            unique = []
            for h in hypotheses:
                key = tuple(h)
                if key not in seen:
                    seen.add(key)
                    unique.append(h)
            hypotheses = unique
        
        return hypotheses
    
    def _update_hypothesis_weights(self):
        """Update weights based on opponent offers using Bayesian reasoning."""
        if not self.opponent_offers or not self.opp_hypotheses:
            return
        
        import math
        
        for h_idx, h in enumerate(self.opp_hypotheses):
            opp_total = sum(h[i] * self.counts[i] for i in range(self.n))
            if opp_total == 0:
                self.hyp_weights[h_idx] = 1e-10
                continue
            
            log_likelihood = 0.0
            for offer in self.opponent_offers:
                # offer = what opponent gives to me
                # opponent keeps counts[i] - offer[i]
                opp_keeps_val = sum(h[i] * (self.counts[i] - offer[i]) for i in range(self.n))
                opp_gives_val = sum(h[i] * offer[i] for i in range(self.n))
                
                # Rational opponent keeps more value - use softmax likelihood
                frac_kept = opp_keeps_val / opp_total
                # Higher fraction kept = more likely for rational agent
                log_likelihood += 3.0 * frac_kept
                
                # Penalize hypotheses where opponent gives away high value items
                if opp_gives_val > opp_total * 0.6:
                    log_likelihood -= 2.0
            
            self.hyp_weights[h_idx] = math.exp(min(50, log_likelihood))
        
        # Normalize
        total_w = sum(self.hyp_weights)
        if total_w > 0:
            self.hyp_weights = [w / total_w for w in self.hyp_weights]
    
    def _get_weighted_opp_values(self):
        """Get weighted average opponent values from hypotheses."""
        if not self.opp_hypotheses:
            return self._fallback_opp_estimate()
        
        self._update_hypothesis_weights()
        
        est = [0.0] * self.n
        for h_idx, h in enumerate(self.opp_hypotheses):
            w = self.hyp_weights[h_idx]
            for i in range(self.n):
                est[i] += w * h[i]
        
        return est
    
    def _fallback_opp_estimate(self):
        """Fallback opponent estimation when hypotheses aren't available."""
        est = [0.0] * self.n
        if not self.opponent_offers:
            total_items = sum(self.counts)
            if total_items > 0:
                for i in range(self.n):
                    est[i] = self.total / total_items
            return est
        
        give_ratio = [0.0] * self.n
        for offer in self.opponent_offers:
            for i in range(self.n):
                if self.counts[i] > 0:
                    give_ratio[i] += offer[i] / self.counts[i]
        
        for i in range(self.n):
            if self.counts[i] > 0 and self.opponent_offers:
                give_ratio[i] /= len(self.opponent_offers)
        
        raw_vals = [0.0] * self.n
        for i in range(self.n):
            if self.counts[i] > 0:
                keep_ratio = 1.0 - give_ratio[i]
                raw_vals[i] = max(0.01, keep_ratio)
        
        raw_total = sum(raw_vals[i] * self.counts[i] for i in range(self.n))
        if raw_total > 0:
            for i in range(self.n):
                est[i] = raw_vals[i] * self.total / raw_total
        
        return est
    
    def _compute_nash_product(self, my_split, opp_vals):
        """Compute Nash bargaining product for a split."""
        mv = self._my_value(my_split)
        ov = self._opp_value_from_my_split(my_split, opp_vals)
        if mv <= 0 or ov <= 0:
            return -1e18
        import math
        return math.log(mv) + math.log(ov)
    
    def _find_pareto_frontier(self, opp_vals):
        """Find Pareto-optimal splits."""
        if not self.all_splits:
            return []
        
        # Group by my_value, keep max opp_value for each
        by_mv = {}
        for s in self.all_splits:
            mv = self._my_value(s)
            ov = self._opp_value_from_my_split(s, opp_vals)
            if mv not in by_mv or ov > by_mv[mv][1]:
                by_mv[mv] = (s, ov)
        
        items = sorted(by_mv.items(), key=lambda x: x[0])
        
        # Filter Pareto frontier
        frontier = []
        max_ov = -1
        for mv, (s, ov) in reversed(items):
            if ov > max_ov:
                frontier.append((mv, ov, s))
                max_ov = ov
        
        frontier.reverse()
        return frontier
    
    def _get_concession_target(self, progress):
        """Get target value fraction based on progress through negotiation."""
        # Be reasonable from the start but don't concede too fast
        if self.total_turns <= 6:
            # Short negotiation - concede faster
            start = 0.80
            end = 0.25
            beta = 1.5
        elif self.total_turns <= 16:
            start = 0.80
            end = 0.20
            beta = 2.0
        else:
            # Long negotiation - be more patient
            start = 0.78
            end = 0.15
            beta = 2.5
        
        concession = progress ** beta
        frac = start - (start - end) * concession
        return self.total * frac
    
    def _find_best_offer(self, target_my_val, opp_vals, progress):
        """Find the best offer to make."""
        import math
        
        if self.all_splits:
            # Score all viable splits
            opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
            
            # Weight: early = favor myself more, late = favor mutual gain
            # But always maintain a reasonable split
            my_weight = max(0.5, 1.2 - 0.5 * progress)
            opp_weight = min(1.0, 0.3 + 0.7 * progress)
            
            best_score = -1e18
            best_split = None
            
            # Also track best by my value for fallback
            best_for_me = None
            best_mv = -1
            
            for s in self.all_splits:
                mv = self._my_value(s)
                ov = self._opp_value_from_my_split(s, opp_vals)
                
                if mv > best_mv:
                    best_mv = mv
                    best_for_me = s
                
                # Must meet minimum target
                if mv < target_my_val * 0.8:
                    continue
                
                if mv <= 0:
                    continue
                
                if ov <= 0:
                    # Opponent will never accept this
                    score = mv * 0.001
                else:
                    # Weighted Nash-like product
                    score = my_weight * math.log(mv + 0.1) + opp_weight * math.log(ov + 0.1)
                    
                    # Bonus for meeting target
                    if mv >= target_my_val:
                        score += 0.5
                
                if score > best_score:
                    best_score = score
                    best_split = s
            
            if best_split is None:
                # Lower bar significantly
                for s in self.all_splits:
                    mv = self._my_value(s)
                    ov = self._opp_value_from_my_split(s, opp_vals)
                    if mv <= 0:
                        continue
                    if ov <= 0:
                        score = mv * 0.001
                    else:
                        score = my_weight * math.log(mv + 0.1) + opp_weight * math.log(ov + 0.1)
                    if score > best_score:
                        best_score = score
                        best_split = s
            
            if best_split is None:
                best_split = best_for_me if best_for_me else tuple(self.counts)
            
            # Avoid exact repeats if we have alternatives
            prev_set = set()
            for prev in self.my_offers:
                prev_set.add(tuple(prev))
            
            if tuple(best_split) in prev_set and len(self.my_offers) >= 2:
                # Find close alternative
                alt_best_score = -1e18
                alt_split = None
                for s in self.all_splits:
                    if tuple(s) in prev_set:
                        continue
                    mv = self._my_value(s)
                    ov = self._opp_value_from_my_split(s, opp_vals)
                    if mv < target_my_val * 0.75 or mv <= 0:
                        continue
                    if ov <= 0:
                        score = mv * 0.001
                    else:
                        score = my_weight * math.log(mv + 0.1) + opp_weight * math.log(ov + 0.1)
                    if score > alt_best_score:
                        alt_best_score = score
                        alt_split = s
                
                # Only use alternative if it's not much worse
                if alt_split is not None and alt_best_score > best_score - 1.0:
                    best_split = alt_split
            
            return list(best_split)
        else:
            return self._find_offer_heuristic(target_my_val, opp_vals, progress)
    
    def _find_offer_heuristic(self, target_my_val, opp_vals, progress):
        """For large search spaces, use heuristic approach."""
        import random
        rng = random.Random(self.turn * 31 + 97)
        
        # Compute efficiency ratio for each item type
        efficiencies = []
        for i in range(self.n):
            my_v = self.values[i]
            op_v = max(0.01, opp_vals[i])
            efficiencies.append((my_v / op_v, i))
        efficiencies.sort(reverse=True)
        
        best_score = -1e18
        best_split = None
        
        import math
        my_weight = max(0.5, 1.2 - 0.5 * progress)
        opp_weight = min(1.0, 0.3 + 0.7 * progress)
        
        for trial in range(3000):
            split = [0] * self.n
            
            if trial == 0:
                # Greedy by efficiency
                for eff, i in efficiencies:
                    split[i] = self.counts[i]
                # Give back low-efficiency items until opponent has reasonable value
                opp_target = self.total * 0.3
                for eff, i in efficiencies:
                    if self._opp_value_from_my_split(split, opp_vals) >= opp_target:
                        break
                    if eff < 1.0 and split[i] > 0:
                        give = min(split[i], max(1, split[i] // 2))
                        split[i] -= give
            elif trial < 10:
                # Variations: take high-efficiency items fully, partially take medium
                cutoff = 0.5 + trial * 0.2
                for eff, i in efficiencies:
                    if eff >= cutoff:
                        split[i] = self.counts[i]
                    elif self.values[i] > 0:
                        split[i] = rng.randint(0, self.counts[i])
            elif trial < 50:
                # Random biased by efficiency
                for i in range(self.n):
                    if self.counts[i] == 0:
                        continue
                    my_v = self.values[i]
                    op_v = max(0.01, opp_vals[i])
                    p = (my_v + 0.05) / (my_v + op_v + 0.1)
                    split[i] = sum(1 for _ in range(self.counts[i]) if rng.random() < p)
            else:
                # Fully random
                for i in range(self.n):
                    split[i] = rng.randint(0, self.counts[i])
            
            mv = self._my_value(split)
            ov = self._opp_value_from_my_split(split, opp_vals)
            
            if mv < target_my_val * 0.7 or mv <= 0:
                continue
            
            if ov <= 0:
                score = mv * 0.001
            else:
                score = my_weight * math.log(mv + 0.1) + opp_weight * math.log(ov + 0.1)
            
            if score > best_score:
                best_score = score
                best_split = split[:]
        
        if best_split is None:
            best_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        return best_split
    
    def _should_accept(self, o, progress):
        """Decide whether to accept opponent's offer."""
        my_val = self._my_value(o)
        turns_left = self.total_turns - self.turn
        my_frac = my_val / max(1, self.total)
        
        if my_val >= self.total:
            return True
        
        if my_val <= 0 and self.total > 0:
            return False
        
        if self.total == 0:
            return True
        
        # Last turn - we can't counter, must accept or get nothing
        # Actually, if turns_left == 0, this IS our last action
        if turns_left <= 0:
            return my_val >= 1
        
        # If we reject, we get to make one more offer (turns_left == 1)
        # But opponent must accept it - risky
        if turns_left == 1:
            return my_frac >= 0.05
        
        # Very few turns left
        if turns_left == 2:
            return my_frac >= 0.10
        
        target = self._get_concession_target(progress)
        
        # Accept if meets target
        if my_val >= target:
            return True
        
        # Accept if >= 50% any time
        if my_frac >= 0.50:
            return True
        
        # Sliding scale acceptance
        if my_frac >= 0.40 and progress >= 0.20:
            return True
        if my_frac >= 0.35 and progress >= 0.35:
            return True
        if my_frac >= 0.30 and progress >= 0.45:
            return True
        if my_frac >= 0.25 and progress >= 0.55:
            return True
        if my_frac >= 0.20 and progress >= 0.65:
            return True
        if my_frac >= 0.15 and progress >= 0.75:
            return True
        if my_frac >= 0.10 and progress >= 0.85:
            return True
        
        # If opponent offers are stagnating and this is close to best we've seen
        if len(self.opponent_offers) >= 3 and progress >= 0.4:
            recent_vals = [self._my_value(x) for x in self.opponent_offers[-4:]]
            best_recent = max(recent_vals)
            if my_val >= best_recent * 0.95 and my_frac >= 0.12:
                # Opponent isn't budging much
                improvement = best_recent - min(recent_vals)
                if improvement <= max(1, self.total * 0.03):
                    return True
        
        return False
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        progress = min(1.0, (self.turn - 1) / max(1, self.total_turns - 1))
        
        if o is not None:
            self.opponent_offers.append(o[:])
            val = self._my_value(o)
            if val > self.best_received_val:
                self.best_received_val = val
                self.best_received = o[:]
            
            if self._should_accept(o, progress):
                return None
        
        # Get opponent value estimates
        opp_vals = self._get_weighted_opp_values()
        
        # Get target based on concession curve
        target = self._get_concession_target(progress)
        
        # Don't start by demanding everything - make a reasonable but favorable first offer
        if self.turn <= 2 and not self.opponent_offers:
            # First offer: aim for ~75-80% of value but give opponent something
            target = self.total * 0.78
        
        # Find best offer
        best = self._find_best_offer(target, opp_vals, progress)
        
        # Near end: if our counter gives us less than best received, adjust
        turns_left = self.total_turns - self.turn
        if turns_left <= 3 and self.best_received is not None:
            my_offer_val = self._my_value(best)
            if my_offer_val < self.best_received_val:
                # Make an offer at least as good as best received for us
                alt_target = self.best_received_val * 1.05
                alt = self._find_best_offer(alt_target, opp_vals, progress)
                if self._my_value(alt) >= self.best_received_val:
                    best = alt
        
        self.my_offers.append(best[:])
        return best