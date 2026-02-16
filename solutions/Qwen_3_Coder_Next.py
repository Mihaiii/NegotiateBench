class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.rounds_remaining = max_rounds
        self.is_first = (me == 0)
        self.opponent_valuations = None  # Will be learned during negotiation
        self.offer_history = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_remaining -= 1
        
        # Record opponent's offer for analysis
        if o is not None:
            self.offer_history.append(o.copy())
        
        # On first turn, make an initial offer
        if o is None:
            return self._make_initial_offer()
        
        # Calculate what we're getting in this offer
        our_value = sum(v * x for v, x in zip(self.values, o))
        
        # Estimate opponent's valuations from their offers
        self._estimate_opponent_valuation()
        
        # Calculate what opponent is getting in this offer
        their_value = sum(self.opponent_valuations[i] * (self.counts[i] - o[i]) 
                         for i in range(len(self.counts)))
        
        # Accept if this is good enough and opponent gets reasonable value
        if self._should_accept(our_value, their_value):
            return None
            
        # Make counter-offer
        return self._make_counter_offer()
    
    def _estimate_opponent_valuation(self):
        """Estimate opponent valuations from their offers"""
        if not self.offer_history:
            # Default: assume opponent values items similarly to us but scaled
            self.opponent_valuations = [max(1, v) for v in self.values]
            return
            
        # Use opponent's latest offer to infer their valuations
        # If they kept item i, it likely has higher value for them
        kept_counts = [0] * len(self.counts)
        total_offers = len(self.offer_history)
        
        for offer in self.offer_history:
            for i in range(len(self.counts)):
                if offer[i] < self.counts[i]:  # Opponent kept item i
                    kept_counts[i] += 1
        
        # Normalize to a reasonable range (1-10)
        max_kept = max(kept_counts) if max(kept_counts) > 0 else 1
        
        # Start with an initial estimate based on our values
        self.opponent_valuations = [max(1, v) for v in self.values]
        
        # Adjust estimates based on opponent behavior
        for i in range(len(self.counts)):
            if kept_counts[i] > 0:
                # If opponent kept this item frequently, it's likely valuable to them
                ratio = kept_counts[i] / total_offers
                # Scale up if they kept it, down if they gave it up often
                self.opponent_valuations[i] = max(1, int(self.opponent_valuations[i] * (1 + ratio * 2)))
    
    def _make_initial_offer(self) -> list[int]:
        """Create initial offer if we go first"""
        offer = [0] * len(self.counts)
        
        # Calculate how much value we need to accept
        target_ratio = 0.6 if self.rounds_remaining >= 6 else 0.5
        
        # Estimate opponent valuations
        self._estimate_opponent_valuation()
        
        # Create sorted list of items by our value and opponent value
        items = []
        for i in range(len(self.counts)):
            opp_val = self.opponent_valuations[i] if self.opponent_valuations else self.values[i]
            # Key insight: give opponent items that are valuable to them but not to us
            items.append((i, self.values[i], opp_val))
        
        # First, ensure opponent gets at least some items they value
        # Sort by opponent value (descending) to prioritize giving them high-value items
        items.sort(key=lambda x: x[2], reverse=True)
        
        # Give opponent items they value highly
        for i, our_val, opp_val in items:
            if opp_val >= our_val and self.counts[i] > 0:
                offer[i] = self.counts[i] - 1  # Keep one for ourselves if valuable
            elif opp_val > our_val:
                offer[i] = 0  # Give all to opponent
            else:
                offer[i] = self.counts[i]  # Keep all
        
        # Calculate our current value
        our_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
        
        # If we have enough value, we're good
        target = int(self.total_value * target_ratio)
        if our_value >= target:
            return offer
            
        # Otherwise, take more items
        # Sort by value ratio (our value / opponent value) descending
        items.sort(key=lambda x: x[1] / max(1, x[2]), reverse=True)
        
        for i, our_val, opp_val in items:
            if our_value >= target:
                break
            if offer[i] < self.counts[i]:
                take = min(self.counts[i] - offer[i], (target - our_value) // max(1, our_val) + 1)
                offer[i] += take
                our_value += take * our_val
        
        return offer
    
    def _make_counter_offer(self) -> list[int]:
        """Create counter-offer after receiving opponent's offer"""
        offer = [0] * len(self.counts)
        
        # Estimate opponent valuations
        self._estimate_opponent_valuation()
        
        # Target value based on rounds remaining
        if self.rounds_remaining <= 1:
            target_ratio = 0.50
        elif self.rounds_remaining <= 3:
            target_ratio = 0.55
        elif self.rounds_remaining <= 6:
            target_ratio = 0.60
        else:
            target_ratio = 0.65
        
        target = int(self.total_value * target_ratio)
        current_value = 0
        
        # Sort items by our value
        items = list(enumerate(self.values))
        items.sort(key=lambda x: x[1], reverse=True)
        
        # First, take all items we value more than opponent (based on estimates)
        for i, our_val in items:
            opp_val = self.opponent_valuations[i] if self.opponent_valuations else our_val
            if our_val > opp_val:
                offer[i] = self.counts[i]
                current_value += self.counts[i] * our_val
        
        # If we need more value, take items where we have comparative advantage
        if current_value < target:
            items.sort(key=lambda x: x[1] / max(1, self.opponent_valuations[x[0]] if self.opponent_valuations else x[1]), reverse=True)
            for i, our_val in items:
                if current_value >= target:
                    break
                if offer[i] < self.counts[i]:
                    take = min(self.counts[i] - offer[i], (target - current_value) // max(1, our_val) + 1)
                    offer[i] += take
                    current_value += take * our_val
        
        # In very late rounds, be more accommodating
        if self.rounds_remaining <= 2:
            # Look at opponent's latest offer and accommodate their requests
            if self.offer_history:
                latest = self.offer_history[-1]
                # For items where opponent gave us few, consider giving them more
                for i in range(len(offer)):
                    if latest[i] < self.counts[i] // 3 and self.values[i] <= self.opponent_valuations[i]:
                        # Give them more of this item
                        offer[i] = min(self.counts[i], latest[i] + (self.counts[i] - latest[i]) // 2)
                        current_value = sum(offer[j] * self.values[j] for j in range(len(offer)))
                        break
        
        return offer
    
    def _should_accept(self, our_value: int, their_value: int) -> bool:
        """Determine if we should accept the current offer"""
        # Accept if we get at least 50% of our total value
        min_acceptable = max(1, int(self.total_value * 0.5))
        
        # Adjust acceptance threshold based on rounds remaining
        if self.rounds_remaining <= 1:
            min_acceptable = max(1, int(self.total_value * 0.35))
        elif self.rounds_remaining <= 3:
            min_acceptable = max(1, int(self.total_value * 0.45))
        elif self.rounds_remaining <= 5:
            min_acceptable = max(1, int(self.total_value * 0.50))
        
        # Accept if we get enough value AND opponent gets reasonable value
        # (preventing them from walking away)
        min_opponent_value = max(1, int(self.total_value * 0.25))
        
        return our_value >= min_acceptable and their_value >= min_opponent_value