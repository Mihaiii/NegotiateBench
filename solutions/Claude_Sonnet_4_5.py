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
            
            if self._should_accept(my_value, turns_left, total_turns):
                return None
        
        new_offer = self._make_offer(turns_left, total_turns)
        self.my_offers.append(new_offer)
        return new_offer
    
    def _should_accept(self, offered_value: int, turns_left: int, total_turns: int) -> bool:
        """Strategic acceptance based on value, time, and opponent behavior."""
        if self.total_value == 0:
            return True
        
        value_ratio = offered_value / self.total_value
        
        # Last turn - accept anything positive
        if turns_left <= 1:
            return offered_value > 0
        
        # Detect stalemate - if offers aren't changing, be ready to compromise
        if len(self.their_offers) >= 3:
            recent_offers = self.their_offers[-3:]
            if recent_offers[-1] == recent_offers[-2] == recent_offers[-3]:
                # They're stuck on same offer - evaluate if reasonable
                if value_ratio >= 0.30 and turns_left <= 6:
                    return True
        
        # Time-based threshold with aggressive late-game concessions
        if turns_left <= 2:
            return value_ratio >= 0.20
        elif turns_left <= 4:
            return value_ratio >= 0.30
        elif turns_left <= 6:
            return value_ratio >= 0.38
        elif turns_left <= 8:
            return value_ratio >= 0.42
        else:
            # Early rounds - be more selective
            return value_ratio >= 0.50
    
    def _make_offer(self, turns_left: int, total_turns: int) -> list[int]:
        """Generate offer with strategic concessions."""
        progress = self.turn / total_turns
        
        # Start at 60%, gradually reduce to 35%
        if turns_left <= 2:
            target_ratio = 0.35
        elif turns_left <= 4:
            target_ratio = 0.40
        elif turns_left <= 6:
            target_ratio = 0.45
        elif turns_left <= 8:
            target_ratio = 0.50
        else:
            target_ratio = 0.60 - progress * 0.15
        
        # Estimate opponent values from their behavior
        opp_values = self._estimate_opponent_values()
        
        # Generate offer trying to maximize our value while being fair
        return self._create_optimal_offer(target_ratio, opp_values)
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's valuation from their offers."""
        n = len(self.counts)
        
        if not self.their_offers:
            # Initial guess: inverse of our values (complementary preferences)
            max_val = max(self.values) if max(self.values) > 0 else 1
            return [max_val - v + 1 for v in self.values]
        
        # Analyze what they consistently keep vs give away
        keep_scores = [0.0] * n
        
        for idx, offer in enumerate(self.their_offers):
            weight = (idx + 1) ** 1.5  # Recent offers weighted more
            for i in range(n):
                they_keep = self.counts[i] - offer[i]
                if self.counts[i] > 0:
                    keep_scores[i] += (they_keep / self.counts[i]) * weight
        
        # Normalize to total value
        total = sum(keep_scores) + 0.001
        estimated = [(score / total) * self.total_value for score in keep_scores]
        
        return estimated
    
    def _create_optimal_offer(self, target_ratio: float, opp_values: list[float]) -> list[int]:
        """Create offer using greedy allocation based on efficiency."""
        target_value = target_ratio * self.total_value
        n = len(self.counts)
        
        # Build item list with efficiency scores
        items = []
        for i in range(n):
            for j in range(self.counts[i]):
                # Efficiency: our value per opponent's value
                opp_val = max(opp_values[i], 0.1)
                efficiency = self.values[i] / opp_val
                items.append((i, efficiency, self.values[i]))
        
        # Sort by efficiency (highest first), break ties by our value
        items.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        # Greedy allocation
        offer = [0] * n
        current_value = 0
        
        for item_idx, _, item_value in items:
            if current_value >= target_value:
                break
            offer[item_idx] += 1
            current_value += item_value
        
        # If we didn't reach target, add more high-value items
        if current_value < target_value:
            sorted_by_value = sorted(range(n), key=lambda x: self.values[x], reverse=True)
            for i in sorted_by_value:
                while offer[i] < self.counts[i] and current_value < target_value:
                    offer[i] += 1
                    current_value += self.values[i]
        
        return offer