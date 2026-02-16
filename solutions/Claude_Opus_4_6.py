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

        # Enumerate all possible splits if feasible
        space_size = 1
        for c in counts:
            space_size *= (c + 1)
            if space_size > 200000:
                break
        
        self.all_splits = None
        if space_size <= 200000:
            self.all_splits = []
            self._enumerate(0, [])
        
        # Generate plausible opponent valuations
        self.opp_hypotheses = self._generate_hypotheses(60)
        self.hyp_weights = [1.0] * len(self.opp_hypotheses)
        
        # Track best offer received
        self.best_offer_val = 0
        self.best_offer = None
        self.last_offer_made = None

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

    def _generate_hypotheses(self, count):
        """Generate plausible opponent value vectors that sum to self.total."""
        import random
        rng = random.Random(12345)
        hypotheses = []
        
        # Items with counts
        non_zero = [i for i in range(self.n) if self.counts[i] > 0]
        if not non_zero:
            return [[0] * self.n]
        
        for _ in range(count * 5):
            if len(hypotheses) >= count:
                break
            vals = [0] * self.n
            # Random allocation of total value
            remaining = self.total
            indices = list(range(self.n))
            rng.shuffle(indices)
            
            for j, i in enumerate(indices):
                if self.counts[i] == 0:
                    vals[i] = 0
                    continue
                if j == len(indices) - 1:
                    # Last item gets remainder
                    per_unit = remaining // self.counts[i] if self.counts[i] > 0 else 0
                    vals[i] = per_unit
                    remaining -= per_unit * self.counts[i]
                else:
                    max_per = remaining // self.counts[i] if self.counts[i] > 0 else 0
                    if max_per > 0:
                        per_unit = rng.randint(0, max_per)
                    else:
                        per_unit = 0
                    vals[i] = per_unit
                    remaining -= per_unit * self.counts[i]
            
            # Check if we used exactly total
            actual = sum(vals[i] * self.counts[i] for i in range(self.n))
            if actual <= self.total and remaining >= 0:
                # Distribute remainder
                if remaining > 0:
                    for i in indices:
                        if self.counts[i] > 0:
                            add = remaining // self.counts[i]
                            if add > 0:
                                vals[i] += add
                                remaining -= add * self.counts[i]
                actual = sum(vals[i] * self.counts[i] for i in range(self.n))
                if actual == self.total:
                    hypotheses.append(vals)
        
        # Add some "mirror" hypotheses (opponent values what I don't)
        mirror = [0] * self.n
        zero_items = [i for i in range(self.n) if self.values[i] == 0 and self.counts[i] > 0]
        nonzero_items = [i for i in range(self.n) if self.values[i] > 0 and self.counts[i] > 0]
        
        if zero_items:
            total_zero_capacity = sum(self.counts[i] for i in zero_items)
            if total_zero_capacity > 0:
                per = self.total // total_zero_capacity
                rem = self.total - per * total_zero_capacity
                for i in zero_items:
                    mirror[i] = per
                # Distribute remainder
                for i in zero_items:
                    if rem >= self.counts[i]:
                        mirror[i] += 1
                        rem -= self.counts[i]
                actual = sum(mirror[i] * self.counts[i] for i in range(self.n))
                if actual == self.total:
                    hypotheses.append(mirror[:])
        
        # Add uniform
        total_items = sum(self.counts)
        if total_items > 0:
            uni = [0] * self.n
            rem = self.total
            for i in range(self.n):
                if self.counts[i] > 0:
                    uni[i] = rem // sum(self.counts[j] for j in range(i, self.n) if self.counts[j] > 0)
                    # Actually simpler: just distribute evenly
            # Simpler uniform
            uni_per = self.total // total_items if total_items > 0 else 0
            uni = [uni_per] * self.n
            actual = sum(uni[i] * self.counts[i] for i in range(self.n))
            diff = self.total - actual
            for i in range(self.n):
                if diff <= 0:
                    break
                if self.counts[i] > 0:
                    add = min(diff // self.counts[i], 3)
                    if add > 0:
                        uni[i] += add
                        diff -= add * self.counts[i]
            actual = sum(uni[i] * self.counts[i] for i in range(self.n))
            if actual == self.total:
                hypotheses.append(uni)
        
        # Inverse of my values
        if self.total > 0:
            max_v = max(self.values) if self.values else 1
            inv = [max(0, max_v - self.values[i]) for i in range(self.n)]
            inv_total = sum(inv[i] * self.counts[i] for i in range(self.n))
            if inv_total > 0:
                scaled = [0] * self.n
                for i in range(self.n):
                    scaled[i] = int(round(inv[i] * self.total / inv_total))
                actual = sum(scaled[i] * self.counts[i] for i in range(self.n))
                # Adjust
                diff = self.total - actual
                for i in range(self.n):
                    if diff == 0:
                        break
                    if self.counts[i] > 0:
                        if diff > 0:
                            scaled[i] += 1
                            diff -= self.counts[i]
                        elif diff < 0:
                            if scaled[i] > 0:
                                scaled[i] -= 1
                                diff += self.counts[i]
                actual = sum(scaled[i] * self.counts[i] for i in range(self.n))
                if actual == self.total and all(s >= 0 for s in scaled):
                    hypotheses.append(scaled)
        
        if not hypotheses:
            hypotheses.append([self.total // max(1, sum(self.counts))] * self.n)
        
        return hypotheses

    def _update_weights(self):
        """Update hypothesis weights based on opponent offers."""
        if not self.opponent_offers:
            return
        
        for h_idx, opp_vals in enumerate(self.opp_hypotheses):
            likelihood = 1.0
            opp_total = sum(opp_vals[i] * self.counts[i] for i in range(self.n))
            if opp_total == 0:
                self.hyp_weights[h_idx] = 0.001
                continue
            
            for offer in self.opponent_offers:
                # offer is what opponent gives to ME
                # opponent keeps counts[i] - offer[i]
                opp_keeps_val = sum(opp_vals[i] * (self.counts[i] - offer[i]) for i in range(self.n))
                # Opponent should offer splits where they keep high value
                frac = opp_keeps_val / opp_total if opp_total > 0 else 0
                # Higher fraction kept = more likely under rational behavior
                # Use softmax-like scoring
                likelihood *= max(0.001, frac ** 2)
            
            self.hyp_weights[h_idx] = max(0.0001, likelihood)
        
        # Normalize
        total_w = sum(self.hyp_weights)
        if total_w > 0:
            self.hyp_weights = [w / total_w for w in self.hyp_weights]

    def _expected_opp_values(self):
        """Get weighted average of opponent values."""
        self._update_weights()
        expected = [0.0] * self.n
        for h_idx, opp_vals in enumerate(self.opp_hypotheses):
            w = self.hyp_weights[h_idx]
            for i in range(self.n):
                expected[i] += w * opp_vals[i]
        return expected

    def _get_candidates(self, min_val=0):
        """Get candidate splits sorted by quality."""
        opp_vals = self._expected_opp_values()
        
        if self.all_splits is not None:
            candidates = []
            for split in self.all_splits:
                mv = self._my_value(split)
                if mv < min_val:
                    continue
                ov = self._opp_value_remainder(split, opp_vals)
                candidates.append((mv, ov, list(split)))
            return candidates, opp_vals
        
        # Heuristic generation for large spaces
        import random
        rng = random.Random(self.turn * 1000 + 42)
        
        candidates = []
        seen = set()
        
        # Sort items by efficiency ratio: my_value / opp_value
        ratios = []
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            my_per = self.values[i]
            op_per = opp_vals[i]
            ratio = (my_per + 0.01) / (op_per + 0.01)
            ratios.append((ratio, i))
        ratios.sort(reverse=True)
        
        # Greedy: take items with best ratio for me first
        # Generate variations by trying different amounts
        for trial in range(500):
            split = [0] * self.n
            
            if trial == 0:
                # Pure greedy: take all of items I value most relative to opponent
                order = [idx for _, idx in ratios]
            else:
                order = [idx for _, idx in ratios]
                # Random perturbation
                for j in range(len(order)):
                    if rng.random() < 0.3:
                        swap = rng.randint(0, len(order) - 1)
                        order[j], order[swap] = order[swap], order[j]
            
            for idx in order:
                if trial == 0:
                    split[idx] = self.counts[idx]
                else:
                    split[idx] = rng.randint(0, self.counts[idx])
            
            key = tuple(split)
            if key in seen:
                continue
            seen.add(key)
            
            mv = self._my_value(split)
            if mv < min_val:
                continue
            ov = self._opp_value_remainder(split, opp_vals)
            candidates.append((mv, ov, list(split)))
        
        # Also add: take everything
        all_split = list(self.counts)
        key = tuple(all_split)
        if key not in seen:
            mv = self._my_value(all_split)
            ov = self._opp_value_remainder(all_split, opp_vals)
            candidates.append((mv, ov, all_split))
        
        # Add: take only valued items
        val_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        key = tuple(val_split)
        if key not in seen:
            mv = self._my_value(val_split)
            ov = self._opp_value_remainder(val_split, opp_vals)
            candidates.append((mv, ov, val_split))
        
        return candidates, opp_vals

    def _pick_offer(self, progress):
        if self.total == 0:
            return list(self.counts)
        
        turns_left = self.total_turns - self.turn
        
        # Determine minimum acceptable value based on progress
        # Start high, concede gradually with acceleration near end
        if self.total_turns <= 4:
            # Very short game - compromise quickly
            base = 0.65
            min_frac = base - (base - 0.25) * (progress ** 0.7)
        elif self.total_turns <= 10:
            base = 0.75
            min_frac = base - (base - 0.20) * (progress ** 0.8)
        else:
            base = 0.80
            min_frac = base - (base - 0.15) * (progress ** 0.9)
        
        min_frac = max(0.10, min(0.90, min_frac))
        min_my_val = self.total * min_frac
        
        candidates, opp_vals = self._get_candidates(min_val=max(1, min_my_val * 0.5))
        
        if not candidates:
            candidates, opp_vals = self._get_candidates(min_val=0)
        
        if not candidates:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        # Score candidates using Nash-like product
        # Balance shifts from favoring self early to being more cooperative later
        best_score = -float('inf')
        best_split = None
        
        for mv, ov, s in candidates:
            if mv < min_my_val and mv < self.total:
                continue
            
            # Nash bargaining with shifting weight
            # Early: prioritize my value; Late: prioritize joint gains
            if mv <= 0 and ov <= 0:
                score = -1000
            else:
                my_w = max(0.1, mv)
                op_w = max(0.1, ov)
                # Weighted geometric mean, shifting toward equal weight
                alpha = 0.65 - 0.25 * progress  # 0.65 early -> 0.40 late
                score = alpha * (mv / max(1, self.total)) + (1 - alpha) * (ov / max(1, self.total))
                # Bonus for Pareto efficiency (high total)
                score += 0.1 * (mv + ov) / max(1, self.total)
            
            if score > best_score:
                best_score = score
                best_split = s
        
        if best_split is None:
            # Fall back: highest my value
            candidates.sort(key=lambda x: -x[0])
            for mv, ov, s in candidates:
                best_split = s
                break
        
        if best_split is None:
            best_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        # Anti-repetition: if we've made the same offer 2+ times, try to vary
        if self.my_offers and len(self.my_offers) >= 2:
            if all(o == best_split for o in self.my_offers[-2:]):
                # Find next best that's different
                scored = []
                for mv, ov, s in candidates:
                    if s == best_split:
                        continue
                    if mv >= min_my_val * 0.85:
                        my_w = max(0.1, mv)
                        op_w = max(0.1, ov)
                        alpha = 0.65 - 0.25 * progress
                        sc = alpha * (mv / max(1, self.total)) + (1 - alpha) * (ov / max(1, self.total))
                        sc += 0.1 * (mv + ov) / max(1, self.total)
                        scored.append((sc, s))
                
                if scored:
                    scored.sort(key=lambda x: -x[0])
                    best_split = scored[0][1]
        
        return best_split

    def _should_accept(self, o, progress):
        my_val = self._my_value(o)
        turns_left = self.total_turns - self.turn
        
        if my_val >= self.total:
            return True
        
        if my_val <= 0 and self.total > 0:
            # Only accept 0 if we're about to get nothing anyway and can't do better
            if turns_left <= 0:
                return False  # 0 = no deal anyway
            return False
        
        # What would we offer next?
        # Don't actually call _pick_offer to avoid side effects; estimate
        if self.total_turns <= 4:
            base = 0.65
            target = base - (base - 0.25) * (progress ** 0.7)
        elif self.total_turns <= 10:
            base = 0.75
            target = base - (base - 0.20) * (progress ** 0.8)
        else:
            base = 0.80
            target = base - (base - 0.15) * (progress ** 0.9)
        
        target = max(0.10, min(0.90, target))
        target_val = self.total * target
        
        # Discount for risk of no deal
        # As turns decrease, increase willingness to accept
        if turns_left <= 0:
            # This is the very last chance
            return my_val >= 1
        elif turns_left <= 1:
            # One more turn at most
            return my_val >= max(1, self.total * 0.08)
        elif turns_left <= 2:
            return my_val >= max(1, self.total * 0.12)
        elif turns_left <= 4:
            return my_val >= max(1, self.total * 0.18)
        
        # Accept if offer meets or exceeds what we'd target
        if my_val >= target_val:
            return True
        
        # Accept if >= 50% of total (fair split)
        if my_val >= self.total * 0.50:
            return True
        
        # Accept if >= 40% and we're past early game
        if my_val >= self.total * 0.40 and progress > 0.25:
            return True
        
        # Accept if >= 30% and we're past midpoint  
        if my_val >= self.total * 0.30 and progress > 0.5:
            return True
        
        # Accept if opponent is getting more generous and offer is reasonable
        if len(self.opponent_offers) >= 2:
            prev_val = self._my_value(self.opponent_offers[-2])
            if my_val > prev_val and my_val >= self.total * 0.25:
                if progress > 0.3:
                    return True
        
        # If best we've ever been offered is this or worse, and time running out
        if turns_left <= 6 and my_val >= max(1, self.total * 0.20):
            return True
        
        return False

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        
        if o is not None:
            self.opponent_offers.append(o[:])
            val = self._my_value(o)
            if val > self.best_offer_val:
                self.best_offer_val = val
                self.best_offer = o[:]
        
        progress = (self.turn - 1) / max(1, self.total_turns - 1)
        
        # Acceptance check
        if o is not None:
            if self._should_accept(o, progress):
                return None
        
        # Generate counter-offer
        best = self._pick_offer(progress)
        self.my_offers.append(best[:])
        self.last_offer_made = best[:]
        return best