class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_turns = 2 * max_rounds
        self.my_total = sum(c * v for c, v in zip(counts, values))
        
        # Sort items by value ascending (least valuable first to give up)
        self.sorted_items = sorted(
            [(v, i) for i, v in enumerate(values)],
            key=lambda x: (x[0], x[1])  # sort by value, then index to break ties
        )
        
        self.turn_count = 0
        self.best_offer_received = 0  # Best value we've been offered
        self.previous_offers = set()  # To avoid repeating our offers
        self.last_offer_value = self.my_total  # Value of our last offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Calculate actual turn number (1-based)
        if self.me == 0:
            actual_turn = 2 * (self.turn_count - 1) + 1
        else:
            actual_turn = 2 * self.turn_count
        remaining_turns = self.total_turns - actual_turn
        
        # Handle case where we value nothing
        if self.my_total == 0:
            if o is not None:
                return None
            return [0] * len(self.counts)
        
        # Process incoming offer
        current_offer_value = 0
        if o is not None:
            # Validate offer first
            valid = True
            for i in range(len(o)):
                if not isinstance(o[i], int) or o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
            
            if valid:
                current_offer_value = sum(oi * vi for oi, vi in zip(o, self.values))
                
                # Update best offer received
                if current_offer_value > self.best_offer_received:
                    self.best_offer_received = current_offer_value
                
                # Acceptance checks
                # 1. If we get everything, accept immediately
                if current_offer_value >= self.my_total:
                    return None
                
                # Calculate dynamic threshold
                # Start at 90%, decrease to 50% by the last turn
                progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
                threshold = self.my_total * (0.9 - 0.4 * progress)
                
                # Never go below the best offer we've received (if it's decent)
                if self.best_offer_received >= 0.4 * self.my_total:
                    threshold = max(threshold, self.best_offer_received)
                
                # Minimum thresholds based on remaining turns
                if remaining_turns > 4:
                    threshold = max(threshold, 0.6 * self.my_total)
                elif remaining_turns > 2:
                    threshold = max(threshold, 0.55 * self.my_total)
                else:
                    threshold = max(threshold, 0.45 * self.my_total)
                
                # On the last turn, make sure we at least get the best offer or 40%
                if actual_turn == self.total_turns:
                    threshold = max(self.best_offer_received, 0.4 * self.my_total)
                
                # Clamp threshold to valid range
                threshold = max(0, min(threshold, self.my_total))
                
                # Accept if current offer meets or exceeds threshold
                if current_offer_value >= threshold:
                    return None
        
        # Generate counter-offer
        # Calculate target value for ourselves
        # Start at 95%, decrease to 60% by the end
        progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
        target_fraction = 0.95 - 0.35 * progress
        
        # Don't target less than the best offer we've received (if decent)
        if self.best_offer_received >= 0.4 * self.my_total:
            target_fraction = max(target_fraction, self.best_offer_received / self.my_total)
        
        # Don't target less than our last offer (hold our ground)
        if self.last_offer_value is not None:
            target_fraction = max(target_fraction, self.last_offer_value / self.my_total)
        
        # Minimum target fractions
        if remaining_turns > 4:
            target_fraction = max(target_fraction, 0.7)
        elif remaining_turns > 2:
            target_fraction = max(target_fraction, 0.6)
        else:
            target_fraction = max(target_fraction, 0.5)
        
        target_fraction = min(target_fraction, 1.0)
        target_value = target_fraction * self.my_total
        target_value = max(0, min(target_value, self.my_total))
        
        # Generate the split
        my_split = self._generate_split(target_value)
        
        # Make sure we don't repeat offers
        split_tuple = tuple(my_split)
        attempts = 0
        while split_tuple in self.previous_offers and attempts < 100:
            # Try to adjust the split slightly while keeping value >= target
            my_split = self._adjust_split(my_split, target_value)
            split_tuple = tuple(my_split)
            attempts += 1
        
        # Calculate the actual value of this split
        split_value = sum(mi * vi for mi, vi in zip(my_split, self.values))
        
        # Update tracking
        self.previous_offers.add(split_tuple)
        self.last_offer_value = split_value
        
        return my_split
    
    def _generate_split(self, target_value: float) -> list[int]:
        # Start with all items
        my_split = self.counts.copy()
        current_value = self.my_total
        
        # If we already meet or are below target, return
        if current_value <= target_value:
            return my_split
        
        # Give up least valuable items first
        for val, idx in self.sorted_items:
            if current_value <= target_value or val <= 0:
                continue
            
            # How many can we give up?
            available = my_split[idx]
            if available == 0:
                continue
            
            # Max number to give up to get as close as possible to target without going below
            max_give = min(available, int((current_value - target_value) // val))
            if max_give > 0:
                my_split[idx] -= max_give
                current_value -= max_give * val
            
            # If we can give up one more without going below a reasonable minimum, do it
            if current_value > target_value and my_split[idx] > 0:
                min_acceptable = max(0.4 * self.my_total, target_value - val)
                if current_value - val >= min_acceptable:
                    my_split[idx] -= 1
                    current_value -= val
        
        return my_split
    
    def _adjust_split(self, current_split: list[int], target_value: float) -> list[int]:
        # Try to find a different split with value >= target_value
        new_split = current_split.copy()
        current_value = sum(mi * vi for mi, vi in zip(new_split, self.values))
        
        # First, try swapping items of same value
        # Group items by their value
        value_groups = {}
        for i, v in enumerate(self.values):
            if v not in value_groups:
                value_groups[v] = []
            value_groups[v].append(i)
        
        for v in value_groups:
            indices = value_groups[v]
            if len(indices) < 2:
                continue
            
            # Try to swap between two items in the same value group
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    idx_a, idx_b = indices[i], indices[j]
                    # Take one from a and give to b, if possible
                    if new_split[idx_a] > 0 and new_split[idx_b] < self.counts[idx_b]:
                        new_split[idx_a] -= 1
                        new_split[idx_b] += 1
                        return new_split
                    # Take one from b and give to a, if possible
                    if new_split[idx_b] > 0 and new_split[idx_a] < self.counts[idx_a]:
                        new_split[idx_b] -= 1
                        new_split[idx_a] += 1
                        return new_split
        
        # If that doesn't work, try to make a small adjustment
        # Find an item we can give up (least valuable)
        for val, idx in self.sorted_items:
            if new_split[idx] > 0 and val > 0:
                # Find an item we can take instead (most valuable, same or lower value)
                for val2, idx2 in reversed(self.sorted_items):
                    if idx2 == idx:
                        continue
                    if new_split[idx2] < self.counts[idx2]:
                        # Check if this keeps us above target
                        new_val = current_value - val + val2
                        if new_val >= max(target_value, 0.4 * self.my_total):
                            new_split[idx] -= 1
                            new_split[idx2] += 1
                            return new_split
        
        # If all else fails, just take all positive value items and adjust
        return self._generate_split(target_value)