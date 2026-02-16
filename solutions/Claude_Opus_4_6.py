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
        
        # Enumerate all possible splits (with size limit)
        self.all_splits = []
        space_size = 1
        for c in counts:
            space_size *= (c + 1)
            if space_size > 200000:
                break
        
        if space_size <= 200000:
            self._enumerate(0, [])
        
        # Opponent value estimation
        self.opp_value_est = [0.0] * self.n
        self.opp_estimated = False
        
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
    
    def _opp_value(self, my_split, opp_vals):
        return sum(opp_vals[i] * (self.counts[i] - my_split[i]) for i in range(self.n))
    
    def _estimate_opponent_values(self):
        """Estimate opponent values from their offers (what they give us reveals what they don't value)."""
        if not self.opponent_offers:
            # Default: assume opponent values things inversely to us
            for i in range(self.n):
                if self.counts[i] > 0:
                    self.opp_value_est[i] = max(0.5, (self.total / sum(self.counts[i] for i in range(self.n)) if sum(self.counts) > 0 else 1))
            return
        
        # Analyze what opponent consistently gives us vs keeps
        # If they give us a lot of item i, they probably don't value it much
        give_ratio = [0.0] * self.n
        for offer in self.opponent_offers:
            for i in range(self.n):
                if self.counts[i] > 0:
                    give_ratio[i] += offer[i] / self.counts[i]
        
        for i in range(self.n):
            if self.counts[i] > 0 and self.opponent_offers:
                give_ratio[i] /= len(self.opponent_offers)
        
        # Items they give away freely are low value to them
        # Items they keep are high value
        # Map keep_ratio to estimated value
        raw_vals = [0.0] * self.n
        for i in range(self.n):
            if self.counts[i] > 0:
                keep_ratio = 1.0 - give_ratio[i]
                raw_vals[i] = keep_ratio  # Higher keep = higher value
        
        # Normalize so total equals self.total
        raw_total = sum(raw_vals[i] * self.counts[i] for i in range(self.n))
        if raw_total > 0:
            for i in range(self.n):
                self.opp_value_est[i] = raw_vals[i] * self.total / raw_total
        else:
            # Uniform
            total_items = sum(self.counts)
            for i in range(self.n):
                self.opp_value_est[i] = self.total / max(1, total_items)
        
        self.opp_estimated = True
    
    def _generate_hypotheses_and_find_best(self):
        """Generate opponent value hypotheses using systematic enumeration."""
        non_zero = [i for i in range(self.n) if self.counts[i] > 0]
        if not non_zero or self.total == 0:
            return [[0] * self.n]
        
        hypotheses = []
        seen = set()
        
        def distribute(remaining, idx, current):
            if len(hypotheses) > 500:
                return
            if idx == len(non_zero):
                if remaining == 0:
                    h = [0] * self.n
                    for j, ii in enumerate(non_zero):
                        h[ii] = current[j]
                    key = tuple(h)
                    if key not in seen:
                        seen.add(key)
                        hypotheses.append(h)
                return
            i = non_zero[idx]
            c = self.counts[i]
            max_per = remaining // c
            for v in range(max_per + 1):
                current.append(v)
                distribute(remaining - v * c, idx + 1, current)
                current.pop()
        
        if len(non_zero) <= 7 and self.total <= 60:
            distribute(self.total, 0, [])
        
        return hypotheses if hypotheses else None
    
    def _score_hypothesis(self, hyp):
        """Score how well a hypothesis explains opponent behavior."""
        if not self.opponent_offers:
            return 1.0
        
        opp_total = sum(hyp[i] * self.counts[i] for i in range(self.n))
        if opp_total == 0:
            return 0.001
        
        score = 0.0
        for offer in self.opponent_offers:
            # offer = what opponent gives to ME
            # opponent keeps counts[i] - offer[i]
            opp_keeps_val = sum(hyp[i] * (self.counts[i] - offer[i]) for i in range(self.n))
            frac = opp_keeps_val / opp_total
            score += frac  # Rational opponents keep high-value items
        
        return score / len(self.opponent_offers)
    
    def _get_best_opp_estimate(self):
        """Get best opponent value estimate using hypotheses if available."""
        hypotheses = self._generate_hypotheses_and_find_best()
        
        if hypotheses and self.opponent_offers:
            # Score each hypothesis
            scored = [(self._score_hypothesis(h), h) for h in hypotheses]
            scored.sort(key=lambda x: -x[0])
            
            # Weighted average of top hypotheses
            top_k = min(20, len(scored))
            top = scored[:top_k]
            
            # Softmax-like weighting
            import math
            max_s = top[0][0]
            weights = []
            for s, h in top:
                w = math.exp(min(50, 5.0 * (s - max_s)))
                weights.append(w)
            total_w = sum(weights)
            
            est = [0.0] * self.n
            for idx, (s, h) in enumerate(top):
                w = weights[idx] / total_w
                for i in range(self.n):
                    est[i] += w * h[i]
            
            return est
        
        # Fallback to ratio-based estimation
        self._estimate_opponent_values()
        return self.opp_value_est[:]
    
    def _find_best_offer(self, target_my_val, opp_vals, progress):
        """Find the best offer achieving at least target_my_val for us."""
        
        if self.all_splits:
            # Score all splits
            opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
            
            candidates = []
            for s in self.all_splits:
                mv = self._my_value(s)
                if mv < target_my_val * 0.85:
                    continue
                ov = self._opp_value(s, opp_vals)
                candidates.append((mv, ov, s))
            
            if not candidates:
                # Lower bar
                for s in self.all_splits:
                    mv = self._my_value(s)
                    if mv >= target_my_val * 0.5:
                        ov = self._opp_value(s, opp_vals)
                        candidates.append((mv, ov, s))
            
            if not candidates:
                # Just get best for me
                best_s = max(self.all_splits, key=lambda s: self._my_value(s))
                return list(best_s)
            
            # Score by Nash bargaining product (weighted)
            # Early: favor my value. Late: favor mutual gain.
            my_weight = 1.0 - 0.3 * progress
            opp_weight = 0.3 + 0.5 * progress
            
            def score(mv, ov):
                if mv <= 0:
                    return -1e9
                if ov <= 0:
                    return mv * 0.1  # Opponent unlikely to accept
                import math
                # Modified Nash: my_value^alpha * opp_value^beta
                return my_weight * math.log(mv + 1) + opp_weight * math.log(ov + 1)
            
            candidates.sort(key=lambda x: -score(x[0], x[1]))
            
            # Avoid repeating same offer too much
            offer_counts = {}
            for prev in self.my_offers:
                key = tuple(prev)
                offer_counts[key] = offer_counts.get(key, 0) + 1
            
            for mv, ov, s in candidates:
                key = tuple(s)
                if offer_counts.get(key, 0) < 2:
                    return list(s)
            
            # If all repeated, pick best anyway
            return list(candidates[0][2])
        else:
            return self._find_offer_large_space(target_my_val, opp_vals, progress)
    
    def _find_offer_large_space(self, target_my_val, opp_vals, progress):
        """For large spaces, use greedy/heuristic approach."""
        import random
        rng = random.Random(self.turn * 13 + 77)
        
        # Compute efficiency: value_to_me / value_to_opponent for each item type
        efficiencies = []
        for i in range(self.n):
            my_v = self.values[i]
            op_v = opp_vals[i] if opp_vals[i] > 0.01 else 0.01
            eff = my_v / op_v
            efficiencies.append((eff, i))
        
        efficiencies.sort(reverse=True)  # I should take items with high ratio first
        
        best_score = -1e9
        best_split = None
        
        for trial in range(2000):
            split = [0] * self.n
            
            if trial == 0:
                # Greedy: take items I value relatively more
                remaining_target = target_my_val
                for eff, i in efficiencies:
                    if remaining_target <= 0:
                        break
                    can_take = min(self.counts[i], 
                                   int(remaining_target / max(1, self.values[i])) + 1 if self.values[i] > 0 else 0)
                    split[i] = can_take
                    remaining_target -= can_take * self.values[i]
            elif trial < 20:
                # Variations of greedy
                threshold = 0.3 + trial * 0.1
                for eff, i in efficiencies:
                    if eff >= threshold:
                        split[i] = self.counts[i]
                    elif self.values[i] > 0:
                        split[i] = max(0, self.counts[i] - rng.randint(0, self.counts[i]))
            else:
                # Random with bias
                for i in range(self.n):
                    if self.counts[i] == 0:
                        continue
                    my_v = self.values[i]
                    op_v = opp_vals[i]
                    # Probability of taking proportional to my value relative to opponent
                    if my_v + op_v > 0:
                        p = (my_v + 0.1) / (my_v + op_v + 0.2)
                    else:
                        p = 0.5
                    for _ in range(self.counts[i]):
                        if rng.random() < p:
                            split[i] += 1
            
            mv = self._my_value(split)
            ov = self._opp_value(split, opp_vals)
            
            if mv < target_my_val * 0.7:
                continue
            
            import math
            if mv > 0 and ov > 0:
                my_w = 1.0 - 0.3 * progress
                op_w = 0.3 + 0.5 * progress
                s = my_w * math.log(mv + 1) + op_w * math.log(ov + 1)
            elif mv > 0:
                s = mv * 0.1
            else:
                s = -1e9
            
            if s > best_score:
                best_score = s
                best_split = split[:]
        
        if best_split is None:
            # Fallback: take everything valuable
            best_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        return best_split
    
    def _get_target_value(self, progress):
        """Concession curve: what's our minimum acceptable value at this progress level."""
        # Boulware-like: concede slowly at first, faster near end
        if self.total_turns <= 4:
            start_frac = 0.85
            end_frac = 0.20
            beta = 2.0
        elif self.total_turns <= 10:
            start_frac = 0.85
            end_frac = 0.15
            beta = 2.5
        else:
            start_frac = 0.85
            end_frac = 0.10
            beta = 3.0
        
        concession = progress ** beta
        target_frac = start_frac - (start_frac - end_frac) * concession
        return self.total * target_frac
    
    def _should_accept(self, o, progress):
        """Decide whether to accept opponent's offer."""
        my_val = self._my_value(o)
        turns_left = self.total_turns - self.turn
        my_frac = my_val / max(1, self.total)
        
        # Always accept full value
        if my_val >= self.total:
            return True
        
        # Never accept 0 unless total is 0
        if my_val <= 0:
            return self.total == 0
        
        # Last possible action - accept anything positive
        if turns_left <= 0:
            return my_val >= 1
        
        # Very end of negotiation
        if turns_left == 1:
            # We can make one more counter-offer, but opponent must accept
            # Risk of getting nothing is high
            return my_frac >= 0.08
        
        if turns_left == 2:
            return my_frac >= 0.12
        
        # Get our target for current progress
        target = self._get_target_value(progress)
        
        # Accept if offer meets or exceeds our target
        if my_val >= target:
            return True
        
        # Accept if >= 50% at any time
        if my_frac >= 0.50:
            return True
        
        # Accept if >= 40% past early game
        if my_frac >= 0.40 and progress >= 0.25:
            return True
        
        # Accept if >= 30% past mid game
        if my_frac >= 0.30 and progress >= 0.45:
            return True
        
        # Accept if >= 20% past 60%
        if my_frac >= 0.20 and progress >= 0.60:
            return True
        
        # Accept if >= 15% past 75%
        if my_frac >= 0.15 and progress >= 0.75:
            return True
        
        # If opponent is not improving and we're running low on time, accept decent offers
        if len(self.opponent_offers) >= 3 and progress >= 0.5:
            recent = [self._my_value(x) for x in self.opponent_offers[-3:]]
            # If opponent isn't improving their offers much
            if max(recent) - min(recent) <= 1 and my_val >= max(recent) * 0.9:
                if my_frac >= 0.15:
                    return True
        
        # Compare to what we could get with next offer
        # If we're unlikely to do better, accept
        if progress >= 0.5 and my_val >= self.best_received_val and my_frac >= 0.15:
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
        
        # Estimate opponent values
        opp_vals = self._get_best_opp_estimate()
        
        # Get target value based on concession curve
        target = self._get_target_value(progress)
        
        # On last turn, if we have a good received offer, consider just re-offering something fair
        turns_left = self.total_turns - self.turn
        
        # Find best offer
        best = self._find_best_offer(target, opp_vals, progress)
        
        # Sanity check: don't offer something worse than what we've been offered
        my_offer_val = self._my_value(best)
        
        # If near end and our offer gives us less than best received, 
        # make a more aggressive but still fair offer
        if turns_left <= 2 and self.best_received is not None:
            if my_offer_val < self.best_received_val:
                # Try to do slightly better than best received
                better_target = self.best_received_val * 1.1
                alt = self._find_best_offer(better_target, opp_vals, progress)
                if self._my_value(alt) >= self.best_received_val:
                    best = alt
        
        self.my_offers.append(best[:])
        return best