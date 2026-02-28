class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.opponent_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            # Validate and calculate offer value
            offer_value = 0
            valid = True
            for i in range(len(o)):
                if o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
                offer_value += o[i] * self.values[i]
            
            if not valid:
                return None
                
            self.opponent_offers.append(o)
            
            # Acceptance thresholds based on time pressure
            if turns_remaining == 1:
                # Last chance - accept any positive offer
                if offer_value > 0:
                    return None
            elif turns_remaining <= 3:
                # Very late - accept 30% or more
                if offer_value >= self.total_value * 0.3:
                    return None
            elif turns_remaining <= 6:
                # Late game - accept 40% or more  
                if offer_value >= self.total_value * 0.4:
                    return None
            else:
                # Early/mid game - accept 50% or more
                if offer_value >= self.total_value * 0.5:
                    return None
        
        # Generate counter-offer
        proposal = [0] * len(self.counts)
        
        # Determine target value based on time pressure
        if turns_remaining == 1:
            target_ratio = 0.3  # Desperate
        elif turns_remaining <= 3:
            target_ratio = 0.4  # Very generous
        elif turns_remaining <= 6:
            target_ratio = 0.5  # Moderate
        elif turns_remaining <= 10:
            target_ratio = 0.6  # Reasonable
        else:
            target_ratio = 0.7  # Aggressive (early game)
            
        target_value = self.total_value * target_ratio
        
        # Simple greedy allocation: take valuable items first
        # Create list of (value_per_item, index) sorted by value descending
        valuable_items = [(self.values[i], i) for i in range(len(self.values)) if self.values[i] > 0]
        valuable_items.sort(reverse=True)
        
        current_value = 0
        
        # Allocate items starting with most valuable
        for value_per_item, idx in valuable_items:
            if current_value >= target_value:
                break
                
            remaining_value_needed = target_value - current_value
            max_items_we_can_take = self.counts[idx]
            
            # Calculate how many items we need
            items_needed = (remaining_value_needed + value_per_item - 1) // value_per_item
            items_to_take = min(max_items_we_can_take, items_needed)
            
            # Special adjustment for first move: don't be too greedy
            if o is None and len(self.opponent_offers) == 0:
                # On first move, leave at least 1 of each valuable item if possible
                if max_items_we_can_take > 1:
                    items_to_take = min(items_to_take, max_items_we_can_take - 1)
            
            proposal[idx] = int(items_to_take)
            current_value += items_to_take * value_per_item
        
        # Ensure we don't exceed counts (safety check)
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        return proposal