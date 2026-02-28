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
            self.all_splits.sort(key=lambda s: self._my_value(s), reverse=True)
        
        # Opponent modeling
        self.opp_hypotheses = []
        self.hyp_weights = []
        self._generate_opp_hypotheses()
        
        # Precompute concession schedule of offers
        self.planned_offers = None
        
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
        non_zero = [i for i in range(self.n) if self.counts[i] > 0]
        if not non_zero or self.total == 0:
            self.opp_hypotheses = [tuple([0] * self.n)]
            self.hyp_weights = [1.0]
            return
        
        hypotheses = []
        
        def distribute(remaining, idx, current):
            if len(hypotheses) > 20000:
                return
            if idx == len(non_zero) - 1:
                i = non_zero[idx]
                c = self.counts[i]
                if c > 0 and remaining >= 0 and remaining % c == 0:
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
        
        if len(non_zero) <= 10 and self.total <= 80:
            distribute(self.total, 0, [])
        
        if not hypotheses:
            import random
            rng = random.Random(42)
            seen = set()
            for _ in range(8000):
                h = [0] * self.n
                remaining = self.total
                order = list(range(self.n))
                rng.shuffle(order)
                valid = True
                for pos, i in enumerate(order):
                    if self.counts[i] == 0:
                        continue
                    last_nonzero = all(self.counts[order[j]] == 0 for j in range(pos + 1, len(order)))
                    if pos == len(order) - 1 or last_nonzero:
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
        if not self.opponent_offers or not self.opp_hypotheses:
            return
        
        import math
        
        new_weights = []
        for h_idx, h in enumerate(self.opp_hypotheses):
            opp_total = sum(h[i] * self.counts[i] for i in range(self.n))
            if opp_total == 0:
                new_weights.append(1e-30)
                continue
            
            log_w = 0.0
            for offer in self.opponent_offers:
                # offer = what opponent gives ME, so opponent keeps counts[i] - offer[i]
                opp_keeps_val = sum(h[i] * (self.counts[i] - offer[i]) for i in range(self.n))
                frac_kept = opp_keeps_val / opp_total
                # Higher temperature for more recent offers
                log_w += 5.0 * frac_kept
            
            log_w = min(300, max(-300, log_w))
            new_weights.append(log_w)
        
        # Normalize in log space
        max_log = max(new_weights)
        exp_weights = []
        for lw in new_weights:
            exp_weights.append(math.exp(lw - max_log))
        
        total_w = sum(exp_weights)
        if total_w > 0:
            self.hyp_weights = [w / total_w for w in exp_weights]
        else:
            self.hyp_weights = [1.0 / len(self.opp_hypotheses)] * len(self.opp_hypotheses)
    
    def _estimated_opp_values(self):
        self._update_weights()
        est = [0.0] * self.n
        for h_idx, h in enumerate(self.opp_hypotheses):
            w = self.hyp_weights[h_idx]
            for i in range(self.n):
                est[i] += w * h[i]
        return est
    
    def _expected_opp_acceptance_prob(self, my_split, opp_vals):
        """Estimate probability opponent accepts based on what they get."""
        opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
        if opp_total <= 0:
            return 0.5
        ov = self._opp_value(my_split, opp_vals)
        frac = ov / opp_total
        # Sigmoid-like acceptance probability
        import math
        # They likely accept if they get >= 30% of their total
        x = (frac - 0.35) * 12
        x = max(-20, min(20, x))
        return 1.0 / (1.0 + math.exp(-x))
    
    def _get_aspiration(self, progress):
        """Return aspiration as fraction of total value. Be firm early, concede late."""
        if self.total_turns <= 2:
            # Single round: be realistic
            return self.total * max(0.40, 0.70 - 0.40 * progress)
        elif self.total_turns <= 6:
            start, end = 0.85, 0.35
        elif self.total_turns <= 16:
            start, end = 0.90, 0.30
        else:
            start, end = 0.92, 0.25
        
        # Concave concession: hold firm longer, concede faster near end
        # Use power curve
        beta = 2.5
        frac = start - (start - end) * (progress ** beta)
        return self.total * frac
    
    def _find_pareto_offers(self, opp_vals):
        """Find Pareto-optimal splits sorted by my value descending."""
        if not self.enumerable:
            return None
        
        # For each possible my_value level, find the split that maximizes opponent value
        pareto = []
        for s in self.all_splits:
            mv = self._my_value(s)
            ov = self._opp_value(s, opp_vals)
            pareto.append((mv, ov, s))
        
        # Sort by my value descending
        pareto.sort(key=lambda x: (-x[0], -x[1]))
        
        # Filter to Pareto frontier
        frontier = []
        best_ov = -1
        for mv, ov, s in pareto:
            if ov > best_ov:
                frontier.append((mv, ov, s))
                best_ov = ov
        
        return frontier
    
    def _generate_offer(self, opp_vals, aspiration, progress):
        """Generate an offer to make."""
        if self.enumerable and self.all_splits:
            return self._generate_offer_enumerable(opp_vals, aspiration, progress)
        else:
            return self._heuristic_offer(opp_vals, aspiration, progress)
    
    def _generate_offer_enumerable(self, opp_vals, aspiration, progress):
        import math
        
        opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
        
        # Find Pareto frontier
        frontier = self._find_pareto_offers(opp_vals)
        
        if not frontier:
            return list(self.all_splits[0]) if self.all_splits else list(self.counts)
        
        # Strategy: pick from Pareto frontier
        # Early: pick highest my_value on frontier
        # Later: move down frontier to increase acceptance probability
        
        # Filter frontier to those meeting aspiration
        candidates = [(mv, ov, s) for mv, ov, s in frontier if mv >= aspiration * 0.85]
        
        if not candidates:
            # Lower bar
            candidates = [(mv, ov, s) for mv, ov, s in frontier if mv >= aspiration * 0.5]
        
        if not candidates:
            candidates = [(mv, ov, s) for mv, ov, s in frontier if mv > 0]
        
        if not candidates:
            return list(self.all_splits[0])
        
        # Score candidates: balance my value with estimated acceptance
        best_score = -1e18
        best_split = None
        
        for mv, ov, s in candidates:
            if mv <= 0:
                continue
            
            # Expected value considering acceptance probability
            if opp_total > 0:
                opp_frac = ov / opp_total
            else:
                opp_frac = 0.5
            
            # Score: my value * soft acceptance factor
            # We want high my value but need opponent to accept
            # As progress increases, weight acceptance more
            acceptance_weight = 0.3 + 0.7 * (progress ** 1.5)
            
            if ov <= 0 and progress < 0.8:
                continue  # Don't offer things opponent gets nothing from early on
            
            score = mv
            if ov > 0 and opp_total > 0:
                score += acceptance_weight * 10 * opp_frac
            elif ov <= 0:
                score -= 50
            
            if score > best_score:
                best_score = score
                best_split = s
        
        if best_split is None:
            # Fallback: best for me on frontier
            best_split = frontier[0][2]
        
        # Avoid exact repetition if we have many turns
        result = list(best_split)
        prev_tuples = set(tuple(p) for p in self.my_offers)
        
        if tuple(result) in prev_tuples and len(self.my_offers) >= 3:
            # Try nearby alternatives on frontier
            for mv, ov, s in candidates:
                if tuple(s) not in prev_tuples and mv >= aspiration * 0.8:
                    alt_score = mv
                    if ov > 0 and opp_total > 0:
                        alt_score += (0.3 + 0.7 * (progress ** 1.5)) * 10 * (ov / opp_total)
                    if alt_score >= best_score * 0.9:
                        result = list(s)
                        break
        
        return result
    
    def _heuristic_offer(self, opp_vals, aspiration, progress):
        import random
        rng = random.Random(self.turn * 37 + 53)
        
        opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
        
        # Compute comparative advantage ratio for each item type
        efficiencies = []
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            mv = self.values[i]
            ov = max(0.001, opp_vals[i])
            efficiencies.append((mv / ov, i, mv, ov))
        efficiencies.sort(reverse=True)
        
        best_score = -1e18
        best_split = None
        
        for trial in range(8000):
            split = [0] * self.n
            
            if trial == 0:
                # Take everything
                for i in range(self.n):
                    split[i] = self.counts[i]
            elif trial == 1:
                # Take items I value, give items I don't
                for i in range(self.n):
                    split[i] = self.counts[i] if self.values[i] > 0 else 0
            elif trial < 10:
                # Greedy by comparative advantage, give back low-efficiency items
                for _, i, mv, ov in efficiencies:
                    split[i] = self.counts[i]
                # Give back items to opponent starting from lowest efficiency
                give_back = trial - 2
                for idx in range(len(efficiencies) - 1, -1, -1):
                    if give_back <= 0:
                        break
                    _, i, mv, ov = efficiencies[idx]
                    split[i] = max(0, split[i] - min(give_back, self.counts[i]))
                    give_back -= 1
            elif trial < 50:
                # Probability-based allocation
                for i in range(self.n):
                    if self.counts[i] == 0:
                        continue
                    mv = self.values[i]
                    ov = max(0.001, opp_vals[i])
                    p = (mv + 0.1) / (mv + ov + 0.2)
                    p = p ** (0.3 + 0.7 * progress)
                    split[i] = sum(1 for _ in range(self.counts[i]) if rng.random() < p)
            else:
                for i in range(self.n):
                    split[i] = rng.randint(0, self.counts[i])
            
            mv = self._my_value(split)
            if mv < aspiration * 0.6:
                continue
            
            ov = self._opp_value(split, opp_vals)
            
            if mv <= 0:
                continue
            if ov <= 0 and progress < 0.8:
                continue
            
            import math
            score = mv
            if ov > 0 and opp_total > 0:
                acceptance_weight = 0.3 + 0.7 * (progress ** 1.5)
                score += acceptance_weight * 10 * (ov / opp_total)
            elif ov <= 0:
                score -= 50
            
            if score > best_score:
                best_score = score
                best_split = split[:]
        
        if best_split is None:
            best_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        return best_split
    
    def _should_accept(self, o, progress):
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
        
        # Accept if meets or exceeds aspiration
        if my_val >= aspiration:
            return True
        
        # Last turn - must accept or get nothing
        if turns_left <= 0:
            return my_val >= 1
        
        if turns_left == 1:
            # We can make one more counter-offer but opponent decides
            # Accept if reasonable
            if my_frac >= 0.20:
                return True
            if my_val >= 1:
                return True  # Something is better than nothing when it's nearly over
            return False
        
        if turns_left == 2:
            return my_frac >= 0.25
        
        # Consider whether we're likely to do better
        # If this is the best offer we've received and we're past midpoint
        if self.best_received is not None and my_val >= self.best_received_val:
            if progress >= 0.6 and my_frac >= 0.30:
                return True
            if progress >= 0.75 and my_frac >= 0.25:
                return True
        
        # Stagnation detection
        if len(self.opponent_offers) >= 4:
            recent_vals = [self._my_value(x) for x in self.opponent_offers[-4:]]
            improving = all(recent_vals[i] <= recent_vals[i + 1] + 1 for i in range(len(recent_vals) - 1))
            max_recent = max(recent_vals)
            min_recent = min(recent_vals)
            
            # Opponent is barely conceding
            if max_recent - min_recent <= max(1, self.total * 0.05):
                if progress >= 0.5 and my_frac >= 0.25:
                    return True
                if progress >= 0.7 and my_frac >= 0.20:
                    return True
        
        # Progressive thresholds - be firmer than before
        thresholds = [
            (0.55, 0.0),   # Accept 55%+ immediately
            (0.50, 0.10),
            (0.45, 0.20),
            (0.40, 0.30),
            (0.35, 0.40),
            (0.30, 0.55),
            (0.25, 0.70),
            (0.20, 0.85),
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
        
        # On the very last turn (if I'm making the last possible offer),
        # make sure it's something the opponent might accept
        turns_left = self.total_turns - self.turn
        if turns_left <= 1:
            opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
            ov = self._opp_value(my_offer, opp_vals)
            mv = self._my_value(my_offer)
            
            # If opponent gets nothing, they'll reject
            if ov < opp_total * 0.15 and opp_total > 0:
                # Find something that gives opponent more while still being good for us
                if self.enumerable:
                    best_last = None
                    best_last_score = -1
                    for s in self.all_splits:
                        smv = self._my_value(s)
                        sov = self._opp_value(s, opp_vals)
                        if sov >= opp_total * 0.20 and smv > best_last_score:
                            best_last_score = smv
                            best_last = s
                    if best_last is not None and best_last_score >= 1:
                        my_offer = list(best_last)
            
            # Also ensure we're not offering less than what we could accept
            if self.best_received is not None:
                if self._my_value(my_offer) < self.best_received_val:
                    # We should have accepted the best received instead
                    # But since we didn't, try to offer something at least as good
                    pass
        
        self.my_offers.append(my_offer[:])
        return my_offer