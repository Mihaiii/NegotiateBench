class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.turn = 0
        self.their_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn + 1
        
        if o is not None:
            self.their_offers.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            if self._should_accept(my_value, turns_left):
                return None
        
        return self._make_offer(turns_left)
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Decide whether to accept with adaptive thresholds."""
        if self.total_value == 0:
            return True
        
        value_ratio = offered_value / self.total_value
        
        # Last turn - accept anything positive
        if turns_left <= 1:
            return offered_value > 0
        
        # Detect if we're stuck in a loop (opponent repeating offers)
        if len(self.their_offers) >= 3:
            if self.their_offers[-1] == self.their_offers[-2] == self.their_offers[-3]:
                # Accept if reasonable and time is running out
                if turns_left <= 4:
                    return value_ratio >= 0.30
                elif turns_left <= 8:
                    return value_ratio >= 0.35
        
        # Dynamic acceptance thresholds based on remaining turns
        if turns_left <= 2:
            threshold = 0.25
        elif turns_left <= 4:
            threshold = 0.33
        elif turns_left <= 8:
            threshold = 0.40
        elif turns_left <= 12:
            threshold = 0.45
        else:
            threshold = 0.50
        
        return value_ratio >= threshold
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Generate strategic offer using Nash bargaining approach."""
        n = len(self.counts)
        
        # Estimate opponent values
        opp_values = self._estimate_opponent_values()
        
        # Calculate target value based on urgency
        if turns_left <= 2:
            target_ratio = 0.35
        elif turns_left <= 4:
            target_ratio = 0.40
        elif turns_left <= 8:
            target_ratio = 0.45
        elif turns_left <= 12:
            target_ratio = 0.50
        else:
            target_ratio = 0.55
        
        # Find Pareto-optimal allocation
        return self._find_optimal_offer(target_ratio, opp_values)
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent values from their offers."""
        n = len(self.counts)
        
        if not self.their_offers:
            # No data - assume complementary values
            max_val = max(self.values) if self.values else 1
            return [max_val - v + 1 for v in self.values]
        
        # Analyze what they consistently keep
        kept_counts = [0.0] * n
        weights_sum = 0.0
        
        for idx, offer in enumerate(self.their_offers):
            weight = (idx + 1) ** 2  # Recent offers weighted more
            for i in range(n):
                they_kept = self.counts[i] - offer[i]
                kept_counts[i] += they_kept * weight
            weights_sum += weight
        
        # Normalize and convert to estimated values
        if weights_sum == 0:
            return [1.0] * n
        
        kept_ratios = [k / weights_sum for k in kept_counts]
        total_kept = sum(kept_ratios)
        
        if total_kept == 0:
            return [1.0] * n
        
        # Distribute total value proportionally
        estimated = [(r / total_kept) * self.total_value for r in kept_ratios]
        
        # Ensure no zeros (for division safety)
        return [max(v, 0.1) for v in estimated]
    
    def _find_optimal_offer(self, target_ratio: float, opp_values: list[float]) -> list[int]:
        """Find offer maximizing Nash product (my_gain * their_gain)."""
        n = len(self.counts)
        target_value = target_ratio * self.total_value
        
        # Try to find allocation that maximizes product of utilities
        best_offer = None
        best_score = -1
        
        # Use dynamic programming for small spaces, greedy for large
        total_items = sum(self.counts)
        
        if total_items <= 15:
            # Enumerate reasonable allocations
            best_offer = self._enumerate_offers(target_value, opp_values)
        
        if best_offer is None:
            # Fall back to greedy based on comparative advantage
            best_offer = self._greedy_offer(target_value, opp_values)
        
        return best_offer
    
    def _enumerate_offers(self, target_value: float, opp_values: list[float]) -> list[int]:
        """Try different allocations to find Nash-optimal."""
        n = len(self.counts)
        
        def generate_allocations(idx, current):
            if idx == n:
                yield current[:]
                return
            for take in range(self.counts[idx] + 1):
                current.append(take)
                yield from generate_allocations(idx + 1, current)
                current.pop()
        
        best_offer = None
        best_score = -1
        opp_total = sum(c * v for c, v in zip(self.counts, opp_values))
        
        for allocation in generate_allocations(0, []):
            my_val = sum(allocation[i] * self.values[i] for i in range(n))
            opp_val = sum((self.counts[i] - allocation[i]) * opp_values[i] for i in range(n))
            
            # Nash product with minimum threshold
            if my_val >= target_value * 0.8:
                score = my_val * opp_val
                if score > best_score:
                    best_score = score
                    best_offer = allocation[:]
        
        return best_offer
    
    def _greedy_offer(self, target_value: float, opp_values: list[float]) -> list[int]:
        """Greedy allocation based on value ratios."""
        n = len(self.counts)
        
        # Create item list with comparative advantage
        items = []
        for i in range(n):
            for _ in range(self.counts[i]):
                my_val = self.values[i]
                their_val = opp_values[i]
                ratio = my_val / their_val if their_val > 0 else my_val * 100
                items.append((i, ratio, my_val))
        
        # Sort by comparative advantage
        items.sort(key=lambda x: (-x[1], -x[2]))
        
        # Allocate greedily
        offer = [0] * n
        current_value = 0
        
        for item_type, _, item_value in items:
            if offer[item_type] < self.counts[item_type]:
                offer[item_type] += 1
                current_value += item_value
                if current_value >= target_value:
                    break
        
        return offer