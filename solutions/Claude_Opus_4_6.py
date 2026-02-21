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
            if space_size > 500000:
                break
        
        self.enumerable = space_size <= 500000
        if self.enumerable:
            self._enumerate(0, [])
        
        # Sort splits by my value descending
        self.all_splits.sort(key=lambda s: self._my_value(s), reverse=True)
        
        # Generate opponent value hypotheses
        self.opp_hypotheses = []
        self.hyp_weights = []
        self._generate_opp_hypotheses()
        
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
    
    def _generate_opp_hypotheses(self):
        """Generate all possible opponent valuations summing to self.total."""
        non_zero = [i for i in range(self.n) if self.counts[i] > 0]
        if not non_zero or self.total == 0:
            self.opp_hypotheses = [tuple([0] * self.n)]
            self.hyp_weights = [1.0]
            return
        
        hypotheses = []
        
        def distribute(remaining, idx, current):
            if len(hypotheses) > 10000:
                return
            if idx == len(non_zero) - 1:
                i = non_zero[idx]
                c = self.counts[i]
                if remaining % c == 0:
                    v = remaining // c
                    h = [0] * self.n
                    for j, ii in enumerate(non_zero[:-1]):
                        h[ii] = current[j]
                    h[i] = v
                    hypotheses.append(tuple(h))
                return
            i = non_zero[idx]
            c = self.counts[i]
            max_per = remaining // c
            for v in range(max_per + 1):
                current.append(v)
                distribute(remaining - v * c, idx + 1, current)
                current.pop()
        
        if len(non_zero) <= 10 and self.total <= 60:
            distribute(self.total, 0, [])
        
        if not hypotheses:
            # Sample hypotheses
            import random
            rng = random.Random(42)
            seen = set()
            for _ in range(5000):
                h = [0] * self.n
                remaining = self.total
                order = list(range(self.n))
                rng.shuffle(order)
                valid = True
                for pos, i in enumerate(order):
                    if self.counts[i] == 0:
                        continue
                    if pos == len(order) - 1 or all(self.counts[order[j]] == 0 for j in range(pos+1, len(order))):
                        if remaining >= 0 and remaining % self.counts[i] == 0:
                            h[i] = remaining // self.counts[i]
                            remaining = 0
                        else:
                            valid = False
                        break
                    else:
                        max_v = remaining // self.counts[i]
                        if max_v >= 0:
                            v = rng.randint(0, max_v)
                            h[i] = v
                            remaining -= v * self.counts[i]
                        else:
                            valid = False
                            break
                if valid and remaining == 0:
                    key = tuple(h)
                    if key not in seen:
                        seen.add(key)
                        hypotheses.append(key)
        
        self.opp_hypotheses = hypotheses if hypotheses else [tuple([0] * self.n)]
        self.hyp_weights = [1.0 / len(self.opp_hypotheses)] * len(self.opp_hypotheses)
    
    def _update_weights(self):
        """Bayesian update of hypothesis weights based on opponent offers."""
        if not self.opponent_offers or not self.opp_hypotheses:
            return
        
        import math
        
        new_weights = []
        for h_idx, h in enumerate(self.opp_hypotheses):
            opp_total = sum(h[i] * self.counts[i] for i in range(self.n))
            if opp_total == 0:
                new_weights.append(1e-20)
                continue
            
            log_likelihood = 0.0
            for offer in self.opponent_offers:
                # offer = what opponent offers to ME
                # opponent keeps counts[i] - offer[i]
                opp_keeps_val = sum(h[i] * (self.counts[i] - offer[i]) for i in range(self.n))
                frac_kept = opp_keeps_val / opp_total
                # Rational opponents keep high fraction of their value
                # Use temperature-scaled likelihood
                log_likelihood += 4.0 * frac_kept
            
            log_likelihood = min(200, log_likelihood)
            new_weights.append(math.exp(log_likelihood))
        
        total_w = sum(new_weights)
        if total_w > 0:
            self.hyp_weights = [w / total_w for w in new_weights]
        else:
            self.hyp_weights = [1.0 / len(self.opp_hypotheses)] * len(self.opp_hypotheses)
    
    def _estimated_opp_values(self):
        """Get expected opponent values."""
        self._update_weights()
        
        est = [0.0] * self.n
        for h_idx, h in enumerate(self.opp_hypotheses):
            w = self.hyp_weights[h_idx]
            for i in range(self.n):
                est[i] += w * h[i]
        return est

    def _score_split(self, split, opp_vals, my_aspiration):
        """Score a split considering both parties' utilities."""
        import math
        mv = self._my_value(split)
        ov = self._opp_value(split, opp_vals)
        opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
        
        if mv <= 0:
            return -1e18, mv, ov
        
        # Nash bargaining product with aspiration adjustment
        if ov <= 0:
            # Opponent won't accept
            return -1e18, mv, ov
        
        # Weighted product: we want high mv but also need ov > 0 for acceptance
        # Use asymmetric Nash: favor ourselves but ensure opponent acceptability
        score = math.log(mv) + 0.6 * math.log(ov + 0.01)
        
        # Bonus for being near aspiration
        if mv >= my_aspiration:
            score += 0.3
        
        return score, mv, ov
    
    def _get_aspiration(self, progress):
        """Aspiration level (what fraction of total I want) declining over time."""
        if self.total_turns <= 4:
            # Very short: be more flexible
            start, end, beta = 0.72, 0.30, 1.2
        elif self.total_turns <= 10:
            start, end, beta = 0.75, 0.25, 1.5
        elif self.total_turns <= 20:
            start, end, beta = 0.78, 0.22, 1.8
        else:
            start, end, beta = 0.80, 0.20, 2.0
        
        frac = start - (start - end) * (progress ** beta)
        return self.total * frac
    
    def _generate_offer(self, opp_vals, aspiration, progress):
        """Generate the best offer to make."""
        import math
        
        if self.enumerable and self.all_splits:
            best_score = -1e18
            best_split = None
            
            for s in self.all_splits:
                score, mv, ov = self._score_split(s, opp_vals, aspiration)
                if mv < aspiration * 0.7:
                    continue
                if score > best_score:
                    best_score = score
                    best_split = s
            
            # If nothing found, lower bar
            if best_split is None:
                for s in self.all_splits:
                    score, mv, ov = self._score_split(s, opp_vals, aspiration * 0.5)
                    if mv <= 0:
                        continue
                    if score > best_score:
                        best_score = score
                        best_split = s
            
            if best_split is None:
                best_split = self.all_splits[0] if self.all_splits else tuple(self.counts)
            
            # Try to avoid repeating exact same offer too many times
            prev_set = set(tuple(p) for p in self.my_offers)
            if tuple(best_split) in prev_set and len(self.my_offers) >= 2:
                alt_best_score = -1e18
                alt_split = None
                for s in self.all_splits:
                    if tuple(s) in prev_set:
                        continue
                    score, mv, ov = self._score_split(s, opp_vals, aspiration)
                    if mv < aspiration * 0.65:
                        continue
                    if score > best_score - 0.5:  # Allow slightly worse alternatives
                        if score > alt_best_score:
                            alt_best_score = score
                            alt_split = s
                if alt_split is not None:
                    best_split = alt_split
            
            return list(best_split)
        else:
            return self._heuristic_offer(opp_vals, aspiration, progress)
    
    def _heuristic_offer(self, opp_vals, aspiration, progress):
        """Heuristic offer for large search spaces."""
        import random
        import math
        rng = random.Random(self.turn * 37 + 53)
        
        # Compute trade efficiency: my_value / opp_value per item
        efficiencies = []
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            mv = self.values[i]
            ov = max(0.001, opp_vals[i])
            efficiencies.append((mv / ov, i))
        efficiencies.sort(reverse=True)
        
        best_score = -1e18
        best_split = None
        
        for trial in range(5000):
            split = [0] * self.n
            
            if trial == 0:
                # Greedy: take items where I have comparative advantage
                for eff, i in efficiencies:
                    split[i] = self.counts[i]
                # Give back least efficient items until opponent gets something
                for eff, i in reversed(efficiencies):
                    ov = self._opp_value(split, opp_vals)
                    opp_total = sum(opp_vals[j] * self.counts[j] for j in range(self.n))
                    if ov >= opp_total * 0.2:
                        break
                    if eff < 0.5:
                        split[i] = 0
            elif trial < 20:
                # Take top-efficiency items, give rest
                take_count = max(1, len(efficiencies) * (20 - trial) // 20)
                for idx, (eff, i) in enumerate(efficiencies):
                    if idx < take_count:
                        split[i] = self.counts[i]
                    elif self.values[i] == 0:
                        split[i] = 0
                    else:
                        split[i] = rng.randint(0, self.counts[i])
            elif trial < 100:
                # Probability-based: higher prob of taking high-efficiency items
                for i in range(self.n):
                    if self.counts[i] == 0:
                        continue
                    mv = self.values[i]
                    ov = max(0.001, opp_vals[i])
                    p = (mv + 0.01) / (mv + ov + 0.02)
                    p = p ** (0.5 + progress)  # Be more generous as time goes on
                    split[i] = sum(1 for _ in range(self.counts[i]) if rng.random() < p)
            else:
                for i in range(self.n):
                    split[i] = rng.randint(0, self.counts[i])
            
            score, mv, ov = self._score_split(split, opp_vals, aspiration)
            if mv < aspiration * 0.6:
                continue
            if score > best_score:
                best_score = score
                best_split = split[:]
        
        if best_split is None:
            # Fallback: take everything I value
            best_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        return best_split
    
    def _should_accept(self, o, progress):
        """Decide whether to accept the opponent's offer."""
        my_val = self._my_value(o)
        
        if self.total == 0:
            return True
        
        if my_val >= self.total:
            return True
        
        if my_val <= 0:
            return False
        
        my_frac = my_val / self.total
        turns_left = self.total_turns - self.turn
        aspiration = self._get_aspiration(progress)
        
        # Accept if meets aspiration
        if my_val >= aspiration:
            return True
        
        # Dynamic acceptance based on turns left
        if turns_left <= 0:
            # This is literally our last chance
            return my_val >= 1
        
        if turns_left == 1:
            # If we reject, we make a counter but opponent may reject
            # Accept if >= 15% or beats some minimum
            return my_frac >= 0.10
        
        if turns_left == 2:
            return my_frac >= 0.15
        
        if turns_left <= 4:
            return my_frac >= 0.20
        
        # General acceptance: if offer is reasonable relative to what we expect to get
        # Consider: if we reject, can we do better?
        # Estimate what we might get from our next offer
        opp_vals = self._estimated_opp_values()
        
        # Check if this is better than what we've been getting
        if self.best_received is not None and my_val >= self.best_received_val:
            # This is the best we've seen - more inclined to accept as time goes on
            if progress >= 0.3 and my_frac >= 0.25:
                return True
            if progress >= 0.5 and my_frac >= 0.20:
                return True
        
        # Stagnation detection
        if len(self.opponent_offers) >= 3:
            recent_vals = [self._my_value(x) for x in self.opponent_offers[-3:]]
            max_recent = max(recent_vals)
            min_recent = min(recent_vals)
            avg_recent = sum(recent_vals) / len(recent_vals)
            
            # If opponent is barely moving and we're past halfway
            if max_recent - min_recent <= max(1, self.total * 0.05) and progress >= 0.4:
                if my_val >= avg_recent * 0.95 and my_frac >= 0.15:
                    return True
        
        # Progressive acceptance thresholds
        thresholds = [
            (0.50, 0.0),   # Accept 50%+ anytime
            (0.40, 0.15),
            (0.35, 0.25),
            (0.30, 0.35),
            (0.25, 0.45),
            (0.20, 0.55),
            (0.15, 0.70),
            (0.10, 0.85),
        ]
        for frac_threshold, prog_threshold in thresholds:
            if my_frac >= frac_threshold and progress >= prog_threshold:
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
        opp_vals = self._estimated_opp_values()
        
        # Get aspiration level
        aspiration = self._get_aspiration(progress)
        
        # Generate offer
        my_offer = self._generate_offer(opp_vals, aspiration, progress)
        
        # Safety check: near end, don't offer less than best received
        turns_left = self.total_turns - self.turn
        if turns_left <= 2 and self.best_received is not None:
            offer_val = self._my_value(my_offer)
            if offer_val < self.best_received_val:
                # Try to find something better for us that opponent might accept
                better = self._generate_offer(opp_vals, self.best_received_val, progress)
                if self._my_value(better) >= self.best_received_val:
                    my_offer = better
        
        self.my_offers.append(my_offer[:])
        return my_offer