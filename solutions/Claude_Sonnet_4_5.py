class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.turn = 0
        self.their_offers = []
        self.last_my_offer = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn + 1
        
        if o is not None:
            self.their_offers.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            if self._should_accept(my_value, turns_left):
                return None
        
        new_offer = self._make_offer(turns_left, total_turns)
        self.last_my_offer = new_offer
        return new_offer
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Decide whether to accept the opponent's offer."""
        if self.total_value == 0:
            return True
        
        value_ratio = offered_value / self.total_value
        
        # Last turn - accept anything positive
        if turns_left <= 1:
            return offered_value > 0
        
        # Detect deadlock - if they keep making same offer, compromise
        if len(self.their_offers) >= 4:
            recent = self.their_offers[-4:]
            if all(off == recent[0] for off in recent):
                # Deadlock detected - accept if reasonable
                if turns_left <= 8 and value_ratio >= 0.25:
                    return True
                if turns_left <= 4 and value_ratio >= 0.20:
                    return True
        
        # Time-based acceptance thresholds with aggressive late-game
        if turns_left <= 2:
            return value_ratio >= 0.15
        elif turns_left <= 4:
            return value_ratio >= 0.25
        elif turns_left <= 6:
            return value_ratio >= 0.33
        elif turns_left <= 10:
            return value_ratio >= 0.40
        elif turns_left <= 16:
            return value_ratio >= 0.45
        else:
            return value_ratio >= 0.50
    
    def _make_offer(self, turns_left: int, total_turns: int) -> list[int]:
        """Generate offer with progressive concessions."""
        
        # Calculate target value ratio with smooth concessions
        progress = (total_turns - turns_left) / total_turns
        
        # Start at 65%, linearly decrease to 30% by the end
        target_ratio = 0.65 - (progress * 0.35)
        
        # Accelerate concessions in final turns
        if turns_left <= 4:
            target_ratio = max(0.30, target_ratio - 0.05 * (4 - turns_left))
        
        # Estimate opponent values
        opp_values = self._estimate_opponent_values()
        
        # Create offer optimizing for Nash product (fairness)
        return self._create_nash_offer(target_ratio, opp_values)
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's valuation from their offers."""
        n = len(self.counts)
        
        if len(self.their_offers) < 2:
            # Initial guess: assume complementary preferences
            total = sum(self.values)
            if total == 0:
                return [1.0] * n
            # Inverse weighting as starting point
            return [(total - v) / max(total, 1) * self.total_value / n for v in self.values]
        
        # Track what they consistently keep vs give
        keep_ratios = [0.0] * n
        weights_sum = 0.0
        
        for idx, offer in enumerate(self.their_offers):
            # Weight recent offers more heavily
            weight = (idx + 1) ** 1.2
            weights_sum += weight
            
            for i in range(n):
                if self.counts[i] > 0:
                    they_keep = self.counts[i] - offer[i]
                    keep_ratios[i] += (they_keep / self.counts[i]) * weight
        
        # Normalize
        if weights_sum > 0:
            keep_ratios = [kr / weights_sum for kr in keep_ratios]
        
        # Convert to estimated values
        total_ratio = sum(keep_ratios) + 0.001
        estimated = [(ratio / total_ratio) * self.total_value for ratio in keep_ratios]
        
        return estimated
    
    def _create_nash_offer(self, target_ratio: float, opp_values: list[float]) -> list[int]:
        """Create offer that balances our value with opponent's likely value."""
        n = len(self.counts)
        target_value = target_ratio * self.total_value
        
        # Build list of all items with their value to us and estimated value to them
        items = []
        for i in range(n):
            for _ in range(self.counts[i]):
                my_val = self.values[i]
                their_val = max(opp_values[i], 0.01)
                # Prefer items we value more relative to them
                efficiency = my_val / their_val
                items.append((i, efficiency, my_val))
        
        # Sort by efficiency (take items we value more than they do)
        items.sort(key=lambda x: (-x[1], -x[2]))
        
        # Greedy allocation
        offer = [0] * n
        current_value = 0
        
        for item_type, _, item_value in items:
            offer[item_type] += 1
            current_value += item_value
            if current_value >= target_value:
                break
        
        # If we overshot or undershot, adjust
        if current_value < target_value * 0.95:
            # Add more high-value items
            for i in sorted(range(n), key=lambda x: -self.values[x]):
                while offer[i] < self.counts[i] and current_value < target_value:
                    offer[i] += 1
                    current_value += self.values[i]
        
        return offer