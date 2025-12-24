class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.opponent_min_offers = None  # Track minimum opponent has offered us
        self.opponent_max_offers = None  # Track maximum opponent has offered us
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count
        
        # Handle incoming offer
        if o is not None:
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # Update opponent offer tracking
            if self.opponent_min_offers is None:
                self.opponent_min_offers = o.copy()
                self.opponent_max_offers = o.copy()
            else:
                for i in range(len(o)):
                    self.opponent_min_offers[i] = min(self.opponent_min_offers[i], o[i])
                    self.opponent_max_offers[i] = max(self.opponent_max_offers[i], o[i])
            
            # Determine acceptance threshold
            if turns_remaining <= 1:
                # Last chance - accept anything reasonable
                min_acceptable = max(1, self.total_value * 0.3)
            elif turns_remaining <= 3:
                min_acceptable = self.total_value * 0.45
            elif turns_remaining <= 6:
                min_acceptable = self.total_value * 0.5
            else:
                # Early rounds - be more selective
                min_acceptable = self.total_value * 0.55
            
            if offer_value >= min_acceptable:
                return None
        
        # Create counter-offer based on remaining time and opponent behavior
        return self._create_counter_offer(turns_remaining)
    
    def _create_counter_offer(self, turns_remaining: int) -> list[int]:
        # Determine our target value based on remaining turns
        if turns_remaining <= 2:
            target_ratio = 0.5
        elif turns_remaining <= 6:
            target_ratio = 0.55
        else:
            target_ratio = 0.6
        
        target_value = self.total_value * target_ratio
        
        # Create list of items we value, sorted by our valuation (descending)
        valuable_items = []
        for i in range(len(self.values)):
            if self.values[i] > 0:
                valuable_items.append((i, self.values[i]))
        
        # Sort by value descending (take most valuable items first)
        valuable_items.sort(key=lambda x: x[1], reverse=True)
        
        # Build offer
        offer = [0] * len(self.counts)
        current_value = 0
        
        # First, try to take items we value most
        for idx, value in valuable_items:
            if current_value >= target_value:
                break
            # Take as many as we can of this item
            items_to_take = self.counts[idx]
            # But be slightly more reasonable if this is not the first round
            if self.turn_count > 1 and turns_remaining > 4:
                # Leave at least one if opponent might value it
                items_to_take = max(0, items_to_take - 1)
            offer[idx] = items_to_take
            current_value += items_to_take * value
        
        # If we're being too greedy and have room to concede, adjust
        if current_value > target_value * 1.2 and turns_remaining <= 10:
            # Reduce our demand slightly
            excess = current_value - target_value
            for idx, value in valuable_items:
                if excess <= 0:
                    break
                if offer[idx] > 0:
                    reduction = min(offer[idx], (excess + value - 1) // value)
                    offer[idx] -= reduction
                    excess -= reduction * value
        
        # Ensure we don't offer nothing when we have valuable items
        if current_value == 0 and self.total_value > 0:
            # Take at least one of our most valuable item
            best_idx = max(range(len(self.values)), key=lambda i: self.values[i])
            if self.values[best_idx] > 0:
                offer[best_idx] = min(1, self.counts[best_idx])
        
        # Validate offer
        for i in range(len(offer)):
            offer[i] = max(0, min(offer[i], self.counts[i]))
        
        return offer