class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.turn = 0
        self.their_offers = []
        self.my_offers = []
        
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
        self.my_offers.append(new_offer)
        return new_offer
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Decide whether to accept the opponent's offer."""
        if self.total_value == 0:
            return True
        
        value_ratio = offered_value / self.total_value
        
        # Last turn - accept anything positive
        if turns_left <= 1:
            return offered_value > 0
        
        # Second to last turn - be very lenient
        if turns_left == 2:
            return value_ratio >= 0.20
        
        # Detect if opponent is being stubborn (same offer 3+ times)
        if len(self.their_offers) >= 3:
            recent = self.their_offers[-3:]
            if all(off == recent[0] for off in recent):
                # They're stuck - accept if reasonable given time left
                if turns_left <= 6:
                    return value_ratio >= 0.30
                elif turns_left <= 12:
                    return value_ratio >= 0.35
        
        # Progressive acceptance thresholds
        if turns_left <= 3:
            return value_ratio >= 0.25
        elif turns_left <= 6:
            return value_ratio >= 0.35
        elif turns_left <= 10:
            return value_ratio >= 0.42
        elif turns_left <= 16:
            return value_ratio >= 0.47
        else:
            return value_ratio >= 0.52
    
    def _make_offer(self, turns_left: int, total_turns: int) -> list[int]:
        """Generate offer with strategic concessions."""
        
        # Estimate opponent values from their behavior
        opp_values = self._estimate_opponent_values()
        
        # Calculate target value based on time pressure
        progress = (total_turns - turns_left) / total_turns
        
        # Start aggressive (70%), concede to fair (50%), then to survival (35%)
        if turns_left <= 3:
            target_ratio = 0.35
        elif turns_left <= 6:
            target_ratio = 0.40
        elif turns_left <= 10:
            target_ratio = 0.45
        else:
            # Smooth decrease from 70% to 50%
            target_ratio = 0.70 - progress * 0.20
        
        # Create efficient offer
        return self._create_efficient_offer(target_ratio, opp_values)
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's valuation from their offers."""
        n = len(self.counts)
        
        if not self.their_offers:
            # No data - assume inverse of our values
            total = sum(self.values)
            if total == 0:
                return [1.0] * n
            return [(total - v) / max(total, 1) * self.total_value / n for v in self.values]
        
        # Weight what they consistently keep vs give
        keep_scores = [0.0] * n
        
        for idx, offer in enumerate(self.their_offers):
            # More recent offers are more informative
            weight = (idx + 1) ** 1.5
            
            for i in range(n):
                if self.counts[i] > 0:
                    they_keep = self.counts[i] - offer[i]
                    keep_scores[i] += (they_keep / self.counts[i]) * weight
        
        # Normalize to sum to total_value
        total_score = sum(keep_scores) + 0.001
        estimated = [(score / total_score) * self.total_value for score in keep_scores]
        
        return estimated
    
    def _create_efficient_offer(self, target_ratio: float, opp_values: list[float]) -> list[int]:
        """Create offer maximizing our value while considering opponent."""
        n = len(self.counts)
        target_value = target_ratio * self.total_value
        
        # Create items with efficiency scores
        items = []
        for i in range(n):
            for _ in range(self.counts[i]):
                my_val = self.values[i]
                their_est_val = max(opp_values[i], 0.01)
                # Prioritize items where we have comparative advantage
                efficiency = my_val / their_est_val if their_est_val > 0 else my_val * 100
                items.append((i, efficiency, my_val))
        
        # Sort by efficiency (prefer items we value more relative to opponent)
        items.sort(key=lambda x: (-x[1], -x[2]))
        
        # Greedy allocation
        offer = [0] * n
        current_value = 0
        
        for item_type, _, item_value in items:
            if current_value >= target_value:
                break
            offer[item_type] += 1
            current_value += item_value
        
        # If we're short, add our most valuable remaining items
        if current_value < target_value * 0.9:
            for i in sorted(range(n), key=lambda x: -self.values[x]):
                while offer[i] < self.counts[i] and current_value < target_value:
                    offer[i] += 1
                    current_value += self.values[i]
        
        # Ensure valid offer
        for i in range(n):
            offer[i] = min(offer[i], self.counts[i])
        
        return offer