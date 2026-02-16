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
        self.total_turns = max_rounds * 2
        
        # Precompute all possible splits
        self.all_splits = self._enumerate_splits()
        # Sort by my value descending
        self.all_splits.sort(key=lambda s: -self._my_value(s))
        
    def _my_value(self, offer):
        return sum(self.values[i] * offer[i] for i in range(self.n))
    
    def _enumerate_splits(self):
        splits = []
        def generate(idx, current):
            if idx == self.n:
                splits.append(current[:])
                return
            for k in range(self.counts[idx] + 1):
                current.append(k)
                generate(idx + 1, current)
                current.pop()
        generate(0, [])
        return splits
    
    def _estimate_opponent_values(self):
        """Estimate opponent's per-unit values from their offer patterns."""
        if not self.opponent_offers:
            return None
        
        # Count how much opponent keeps (counts - offered_to_me) across all offers
        n_offers = len(self.opponent_offers)
        avg_kept = [0.0] * self.n
        for offer in self.opponent_offers:
            for i in range(self.n):
                avg_kept[i] += (self.counts[i] - offer[i])
        
        for i in range(self.n):
            avg_kept[i] /= n_offers
        
        # Weight by proportion kept
        total_items = sum(self.counts)
        if total_items == 0:
            return None
        
        # Estimate relative importance: fraction kept * count weight
        raw_scores = [0.0] * self.n
        for i in range(self.n):
            if self.counts[i] > 0:
                raw_scores[i] = avg_kept[i] / self.counts[i]
            else:
                raw_scores[i] = 0
        
        # Also look at recent offers more heavily (exponential weighting)
        if n_offers >= 2:
            weighted_kept = [0.0] * self.n
            total_weight = 0.0
            for idx, offer in enumerate(self.opponent_offers):
                w = 1.0 + idx  # more recent = higher weight
                total_weight += w
                for i in range(self.n):
                    weighted_kept[i] += w * (self.counts[i] - offer[i])
            for i in range(self.n):
                if self.counts[i] > 0:
                    raw_scores[i] = (weighted_kept[i] / total_weight) / self.counts[i]
        
        total_raw = sum(raw_scores[i] * self.counts[i] for i in range(self.n))
        if total_raw <= 0:
            return None
        
        # Scale so total opponent value = self.total (same total assumption)
        est = []
        for i in range(self.n):
            est.append(raw_scores[i] / total_raw * self.total)
        return est
    
    def _opp_value(self, my_split, opp_vals):
        """Estimate opponent's value for their share."""
        return sum(opp_vals[i] * (self.counts[i] - my_split[i]) for i in range(self.n))
    
    def _find_best_splits(self, min_my_value, opp_vals, top_k=20):
        """Find splits that maximize a combination of my value and opponent value."""
        candidates = []
        for split in self.all_splits:
            mv = self._my_value(split)
            if mv < min_my_value:
                continue
            if opp_vals:
                ov = self._opp_value(split, opp_vals)
            else:
                # Heuristic: prefer giving away zero-value items
                ov = 0
                for i in range(self.n):
                    if self.values[i] == 0:
                        ov += (self.counts[i] - split[i])
                    # Penalize keeping items that might be valuable to opponent
                    # (items with low value to us)
            candidates.append((mv, ov, split))
        
        if not candidates:
            return []
        
        # Sort: primary by my value desc, secondary by opponent value desc
        # Use Nash-bargaining style: maximize mv * ov
        candidates.sort(key=lambda x: (-(x[0] * max(x[1], 0.01)), -x[0]))
        return candidates[:top_k]
    
    def _pick_offer(self, progress):
        """Pick the best offer given current negotiation progress."""
        opp_vals = self._estimate_opponent_values()
        
        # Concession curve: start demanding, gradually concede
        # Use a smooth curve
        if self.total == 0:
            return self.counts[:]
        
        # Target fraction of total value for myself
        # Starts high, decreases smoothly
        if progress < 0.3:
            target_frac = 0.85 - 0.3 * progress
        elif progress < 0.7:
            target_frac = 0.76 - 0.5 * (progress - 0.3)
        else:
            target_frac = 0.56 - 0.6 * (progress - 0.7)
        
        target_frac = max(0.25, min(0.90, target_frac))
        min_my_value = self.total * target_frac
        
        candidates = self._find_best_splits(min_my_value, opp_vals, top_k=50)
        
        if not candidates:
            # Lower threshold
            candidates = self._find_best_splits(self.total * 0.2, opp_vals, top_k=50)
        
        if not candidates:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        # Avoid repeating the same offer more than twice in a row
        best = candidates[0][2]
        if len(self.my_offers) >= 2 and all(o == best for o in self.my_offers[-2:]):
            for mv, ov, split in candidates[1:]:
                if split != best:
                    best = split
                    break
        
        return best
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        
        if o is not None:
            self.opponent_offers.append(o[:])
        
        progress = (self.turn - 1) / max(1, self.total_turns - 1)
        turns_left = self.total_turns - self.turn
        is_last_turn = turns_left <= 0
        
        opp_vals = self._estimate_opponent_values()
        
        # Acceptance logic
        if o is not None:
            my_val = self._my_value(o)
            
            # Always accept if we get everything
            if my_val >= self.total:
                return None
            
            # Dynamic acceptance threshold
            if is_last_turn:
                # Last chance - accept anything positive
                accept_thresh = max(1, self.total * 0.05)
            elif turns_left <= 1:
                accept_thresh = self.total * 0.15
            elif turns_left <= 2:
                accept_thresh = self.total * 0.20
            elif turns_left <= 4:
                accept_thresh = self.total * 0.25
            else:
                accept_thresh = self.total * max(0.30, 0.60 - 0.4 * progress)
            
            if my_val >= accept_thresh:
                # Compare with what we'd likely offer next
                next_offer = self._pick_offer(progress)
                next_val = self._my_value(next_offer)
                
                # If opponent would need to accept our next offer for us to get more,
                # and we're running low on time, accept
                if my_val >= next_val * 0.85 or turns_left <= 2:
                    if my_val >= accept_thresh:
                        return None
                
                # If offer is >= 40% of total, accept
                if my_val >= self.total * 0.40:
                    return None
                
                # If we're past halfway and offer meets threshold
                if progress > 0.4 and my_val >= accept_thresh:
                    return None
                
                # Check if opponent is getting more generous
                if len(self.opponent_offers) >= 2:
                    prev_val = self._my_value(self.opponent_offers[-2])
                    if my_val >= prev_val and my_val >= accept_thresh:
                        return None
                
                if my_val >= accept_thresh:
                    return None
        
        # Generate our counter-offer
        best = self._pick_offer(progress)
        self.my_offers.append(best[:])
        return best