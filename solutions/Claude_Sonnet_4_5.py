class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.my_offers = []
        self.their_offers = []
        self.me = me
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn_count + 1
        
        if o is not None:
            self.their_offers.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            if self._should_accept(my_value, turns_left):
                return None
        
        counter = self._make_offer(turns_left)
        self.my_offers.append(counter)
        return counter
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Decide whether to accept an offer."""
        if turns_left <= 1:
            return offered_value > 0
        
        # More aggressive acceptance thresholds
        progress = 1.0 - (turns_left / (self.max_rounds * 2))
        
        # Start at 55% and decrease to 25%
        if turns_left <= 2:
            threshold = 0.20
        elif turns_left <= 4:
            threshold = 0.30
        elif turns_left <= 8:
            threshold = 0.40
        else:
            threshold = 0.55 - (0.30 * progress)
        
        # If opponent is making good offers, accept
        if len(self.their_offers) >= 2:
            prev_value = sum(self.their_offers[-2][i] * self.values[i] for i in range(len(self.values)))
            # If they're improving their offer
            if offered_value > prev_value and offered_value >= self.total_value * (threshold - 0.05):
                return True
        
        # If opponent is stuck on same offer and it's reasonable, accept
        if len(self.their_offers) >= 3:
            recent = [sum(o[i] * self.values[i] for i in range(len(o))) for o in self.their_offers[-3:]]
            if max(recent) - min(recent) <= self.total_value * 0.05:
                # They're not budging
                if offered_value >= self.total_value * max(0.25, threshold - 0.15):
                    return True
        
        return offered_value >= self.total_value * threshold
    
    def _estimate_opponent_values(self) -> list[int]:
        """Estimate opponent's valuation based on their offers."""
        if not self.their_offers:
            # Assume they value items inversely to us
            max_val = max(self.values) if self.values else 1
            return [max(0, max_val - v) for v in self.values]
        
        # Analyze what they keep vs give
        n = len(self.counts)
        importance = [0.0] * n
        
        for offer in self.their_offers:
            for i in range(n):
                # What they keep for themselves
                kept = self.counts[i] - offer[i]
                if self.counts[i] > 0:
                    importance[i] += kept / self.counts[i]
        
        # Normalize
        total_importance = sum(importance) or 1
        estimated = [int(self.total_value * imp / total_importance) for imp in importance]
        
        # Ensure reasonable values
        for i in range(n):
            if self.counts[i] > 0:
                estimated[i] = max(0, estimated[i])
        
        return estimated
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Generate strategic counter-offer."""
        # Calculate target value that decreases over time
        if turns_left <= 2:
            target_ratio = 0.40
        elif turns_left <= 4:
            target_ratio = 0.45
        elif turns_left <= 8:
            target_ratio = 0.50
        else:
            progress = 1.0 - (turns_left / (self.max_rounds * 2))
            target_ratio = 0.60 - (0.15 * progress)
        
        # Adapt based on opponent's stubbornness
        if len(self.their_offers) >= 4:
            recent = self.their_offers[-4:]
            values = [sum(o[i] * self.values[i] for i in range(len(o))) for o in recent]
            variance = max(values) - min(values)
            
            if variance < self.total_value * 0.10:
                # Opponent is very stubborn, concede more
                target_ratio -= 0.10
            
            # If opponent keeps offering us very little, be more aggressive
            avg_offer = sum(values) / len(values)
            if avg_offer < self.total_value * 0.25:
                target_ratio = max(target_ratio, 0.45)
        
        target_value = target_ratio * self.total_value
        
        # Get opponent value estimates
        opp_values = self._estimate_opponent_values()
        
        # Create priority list for items
        item_priorities = []
        for i in range(len(self.counts)):
            my_val = self.values[i]
            opp_val = opp_values[i]
            
            # Priority: high value for me, low value for opponent
            if opp_val > 0:
                priority = (my_val / (opp_val + 1)) * my_val
            else:
                priority = my_val * 100
            
            item_priorities.append((priority, my_val, opp_val, i))
        
        item_priorities.sort(reverse=True)
        
        # Build offer greedily
        offer = [0] * len(self.counts)
        current_value = 0
        
        # First pass: take high-priority items
        for priority, my_val, opp_val, idx in item_priorities:
            available = self.counts[idx]
            for _ in range(available):
                if current_value >= target_value:
                    break
                offer[idx] += 1
                current_value += my_val
            if current_value >= target_value:
                break
        
        # Ensure offer is valid and reasonable
        if current_value < self.total_value * 0.20:
            # Too little - take all items we value
            offer = [self.counts[i] if self.values[i] > 0 else 0 for i in range(len(self.counts))]
        
        # Make sure we're not being too greedy in later rounds
        if turns_left <= 4:
            offer_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
            if offer_value > self.total_value * 0.60:
                # Scale back
                scale = 0.50 / (offer_value / self.total_value)
                new_offer = [0] * len(offer)
                items = []
                for i in range(len(offer)):
                    for _ in range(offer[i]):
                        items.append(i)
                
                target = int(len(items) * scale)
                for i in range(min(target, len(items))):
                    new_offer[items[i]] += 1
                
                if sum(new_offer[i] * self.values[i] for i in range(len(new_offer))) >= self.total_value * 0.35:
                    offer = new_offer
        
        return offer