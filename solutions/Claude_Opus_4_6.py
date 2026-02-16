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
        
        # Check if enumeration is feasible
        space_size = 1
        for c in counts:
            space_size *= (c + 1)
            if space_size > 500000:
                break
        
        if space_size <= 500000:
            self.all_splits = self._enumerate_splits()
        else:
            self.all_splits = None
        
        # Precompute my values for all splits if enumerated
        if self.all_splits is not None:
            self.split_values = [self._my_value(s) for s in self.all_splits]
    
    def _my_value(self, offer):
        return sum(self.values[i] * offer[i] for i in range(self.n))
    
    def _opp_value_of_remainder(self, my_split, opp_vals):
        return sum(opp_vals[i] * (self.counts[i] - my_split[i]) for i in range(self.n))
    
    def _enumerate_splits(self):
        splits = []
        def generate(idx, current):
            if idx == self.n:
                splits.append(tuple(current))
                return
            for k in range(self.counts[idx] + 1):
                current.append(k)
                generate(idx + 1, current)
                current.pop()
        generate(0, [])
        return splits
    
    def _estimate_opponent_values(self):
        if not self.opponent_offers:
            return None
        
        n_offers = len(self.opponent_offers)
        
        # What opponent gives to themselves = counts - what they offer us
        # Weight recent offers more
        weighted_kept = [0.0] * self.n
        total_weight = 0.0
        for idx, offer in enumerate(self.opponent_offers):
            w = 1.0 + idx * 2.0  # Recent offers weighted much more
            total_weight += w
            for i in range(self.n):
                weighted_kept[i] += w * (self.counts[i] - offer[i])
        
        # Normalize: fraction of each type kept
        frac_kept = [0.0] * self.n
        for i in range(self.n):
            if self.counts[i] > 0:
                frac_kept[i] = weighted_kept[i] / (total_weight * self.counts[i])
        
        # Also look at what they NEVER give us - strong signal of high value
        min_given = [self.counts[i] for i in range(self.n)]
        max_given = [0] * self.n
        for offer in self.opponent_offers:
            for i in range(self.n):
                min_given[i] = min(min_given[i], offer[i])
                max_given[i] = max(max_given[i], offer[i])
        
        # Boost score for items they never fully give
        for i in range(self.n):
            if self.counts[i] > 0:
                # If they always keep some, boost
                always_kept = self.counts[i] - max_given[i]
                if always_kept > 0:
                    frac_kept[i] = max(frac_kept[i], 0.8)
                # If they sometimes give all, they probably don't value it
                if min_given[i] == self.counts[i]:
                    frac_kept[i] = min(frac_kept[i], 0.1)
        
        # Convert to estimated per-unit values
        raw = [frac_kept[i] for i in range(self.n)]
        total_raw = sum(raw[i] * self.counts[i] for i in range(self.n))
        
        if total_raw <= 0:
            # Uniform assumption
            total_items = sum(self.counts)
            if total_items == 0:
                return None
            return [self.total / total_items] * self.n
        
        # Scale to match total
        est = [raw[i] / total_raw * self.total for i in range(self.n)]
        return est
    
    def _generate_smart_splits(self, min_my_val, opp_vals, max_candidates=200):
        """Generate good candidate splits without full enumeration."""
        if self.all_splits is not None:
            candidates = []
            for idx, split in enumerate(self.all_splits):
                mv = self.split_values[idx]
                if mv < min_my_val:
                    continue
                if opp_vals:
                    ov = self._opp_value_of_remainder(split, opp_vals)
                else:
                    ov = sum((self.counts[i] - split[i]) for i in range(self.n) if self.values[i] == 0)
                candidates.append((mv, ov, list(split)))
            return candidates
        
        # For large spaces, use greedy/heuristic generation
        candidates = []
        
        # Sort items by value ratio (my_value vs opponent_value per unit)
        if opp_vals:
            ratios = []
            for i in range(self.n):
                my_v = self.values[i]
                op_v = opp_vals[i]
                # Higher ratio = I value more relative to opponent
                ratio = (my_v + 0.01) / (op_v + 0.01)
                ratios.append((ratio, i))
            ratios.sort(reverse=True)
        else:
            ratios = [(self.values[i] + 0.01, i) for i in range(self.n)]
            ratios.sort(reverse=True)
        
        # Greedy: take items I value most relative to opponent first
        import random
        rng = random.Random(42)
        
        for trial in range(max_candidates * 3):
            split = [0] * self.n
            my_val = 0
            
            if trial == 0:
                # Pure greedy
                order = [idx for _, idx in ratios]
            else:
                # Randomized greedy
                order = [idx for _, idx in ratios]
                # Shuffle with some randomness but keep roughly sorted
                for j in range(len(order)):
                    swap = rng.randint(max(0, j-2), min(len(order)-1, j+2))
                    order[j], order[swap] = order[swap], order[j]
            
            remaining_val = self.total - my_val
            for idx in order:
                # Try taking different amounts
                for k in range(self.counts[idx], -1, -1):
                    added = k * self.values[idx]
                    if my_val + added <= self.total:
                        split[idx] = k
                        my_val += added
                        break
            
            if my_val >= min_my_val:
                if opp_vals:
                    ov = self._opp_value_of_remainder(split, opp_vals)
                else:
                    ov = sum((self.counts[i] - split[i]) for i in range(self.n) if self.values[i] == 0)
                candidates.append((my_val, ov, split))
            
            if len(candidates) >= max_candidates:
                break
        
        # Also add: take everything I value, give rest
        greedy_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        mv = self._my_value(greedy_split)
        if opp_vals:
            ov = self._opp_value_of_remainder(greedy_split, opp_vals)
        else:
            ov = 0
        candidates.append((mv, ov, greedy_split))
        
        # Deduplicate
        seen = set()
        unique = []
        for mv, ov, s in candidates:
            key = tuple(s)
            if key not in seen:
                seen.add(key)
                unique.append((mv, ov, s))
        
        return unique
    
    def _find_pareto_optimal(self, candidates):
        """Find Pareto-optimal splits (no split dominates in both my and opp value)."""
        if not candidates:
            return []
        # Sort by my value descending
        candidates.sort(key=lambda x: -x[0])
        pareto = []
        best_ov = -1
        for mv, ov, s in candidates:
            if ov > best_ov:
                pareto.append((mv, ov, s))
                best_ov = ov
        return pareto
    
    def _pick_offer(self, progress):
        if self.total == 0:
            return list(self.counts)
        
        opp_vals = self._estimate_opponent_values()
        
        # Concession curve: what fraction of total I demand
        # Be more aggressive early, concede smoothly
        if self.total_turns <= 4:
            # Short game - be more willing to compromise
            target_frac = 0.70 - 0.35 * progress
        elif self.total_turns <= 10:
            target_frac = 0.75 - 0.35 * progress
        else:
            # Long game - can be more patient but still concede
            target_frac = 0.80 - 0.40 * progress
        
        target_frac = max(0.20, min(0.85, target_frac))
        min_my_value = self.total * target_frac
        
        candidates = self._generate_smart_splits(min_my_value, opp_vals)
        
        if not candidates:
            # Lower threshold significantly
            candidates = self._generate_smart_splits(self.total * 0.15, opp_vals)
        
        if not candidates:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        # Find Pareto-optimal frontier
        pareto = self._find_pareto_optimal(candidates)
        if not pareto:
            pareto = candidates
        
        # Score using Nash bargaining product, with a bonus for my value
        # Nash: maximize (my_val) * (opp_val) but weight my value a bit more
        best_score = -1
        best_split = None
        
        # Adjust alpha based on progress - early favor myself, later favor joint
        alpha = 0.6 - 0.2 * progress  # 0.6 early, 0.4 late
        
        for mv, ov, s in pareto:
            if mv < min_my_value:
                continue
            # Weighted Nash product
            score = (mv ** alpha) * (max(ov, 0.1) ** (1 - alpha))
            if score > best_score:
                best_score = score
                best_split = s
        
        if best_split is None:
            # Fall back to highest my value from all candidates
            candidates.sort(key=lambda x: (-x[0], -x[1]))
            best_split = candidates[0][2]
        
        # Avoid exact repetition too many times
        if len(self.my_offers) >= 3:
            last_three = self.my_offers[-3:]
            if all(o == best_split for o in last_three):
                # Try next best option
                for mv, ov, s in pareto:
                    if s != best_split and mv >= min_my_value * 0.9:
                        best_split = s
                        break
        
        return best_split
    
    def _should_accept(self, o, progress):
        my_val = self._my_value(o)
        turns_left = self.total_turns - self.turn
        
        if my_val >= self.total:
            return True
        
        if my_val <= 0:
            return False
        
        # Dynamic threshold based on turns left
        if turns_left <= 0:
            # Absolute last turn
            return my_val >= max(1, self.total * 0.01)
        elif turns_left <= 1:
            threshold = self.total * 0.10
        elif turns_left <= 2:
            threshold = self.total * 0.15
        elif turns_left <= 4:
            threshold = self.total * 0.20
        elif self.total_turns <= 6:
            # Short game
            threshold = self.total * (0.35 - 0.15 * progress)
        else:
            threshold = self.total * (0.45 - 0.25 * progress)
        
        threshold = max(1, threshold)
        
        if my_val < threshold:
            return False
        
        # Compare to what we'd offer next
        next_offer = self._pick_offer(progress)
        next_val = self._my_value(next_offer)
        
        # If what they offer is close to what we'd demand anyway, accept
        if my_val >= next_val:
            return True
        
        # If offer is at least 40% of total, strongly consider
        if my_val >= self.total * 0.40:
            # Accept if we're past early game or running low on time
            if progress > 0.2 or turns_left <= 4:
                return True
        
        # If offer is at least 50% of total, accept readily
        if my_val >= self.total * 0.50:
            return True
        
        # Check if opponent is getting more generous
        if len(self.opponent_offers) >= 2:
            prev_val = self._my_value(self.opponent_offers[-2])
            if my_val > prev_val and my_val >= threshold:
                return True
        
        # If close to our next offer value and past midpoint
        if my_val >= next_val * 0.90 and progress > 0.3:
            return True
        
        # General acceptance if meets threshold
        if my_val >= threshold and progress > 0.4:
            return True
        
        # Getting late - lower bar
        if turns_left <= 6 and my_val >= self.total * 0.25:
            return True
        
        return False
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        
        if o is not None:
            self.opponent_offers.append(o[:])
        
        progress = (self.turn - 1) / max(1, self.total_turns - 1)
        
        # Acceptance check
        if o is not None:
            if self._should_accept(o, progress):
                return None
        
        # Generate counter-offer
        best = self._pick_offer(progress)
        self.my_offers.append(best[:])
        return best