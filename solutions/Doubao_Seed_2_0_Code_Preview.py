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
            key=lambda x: (x[0], x[1])
        )
        
        self.turn_count = 0
        self.best_offer_received = 0  # Best value we've been offered
        self.previous_offers = set()  # To avoid repeating our offers
        
        # Track partner's behavior to infer their values
        self.partner_keep_counts = [0] * len(counts)  # Total items partner kept in their offers
        self.partner_offer_count = 0  # Number of offers partner has made

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
                
                # Update partner tracking
                self.partner_offer_count += 1
                for i in range(len(o)):
                    self.partner_keep_counts[i] += (self.counts[i] - o[i])
                
                # Acceptance checks
                # 1. If we get everything, accept immediately
                if current_offer_value >= self.my_total:
                    return None
                
                # 2. If it's the last turn, accept anything better than 0
                if actual_turn == self.total_turns:
                    if current_offer_value >= 0:
                        return None
                
                # Calculate dynamic acceptance threshold
                progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
                # Start at 80%, decrease to 50% by the end
                threshold = self.my_total * (0.8 - 0.3 * progress)
                
                # Never go below the best offer we've received (if it's decent)
                if self.best_offer_received >= 0.2 * self.my_total:
                    threshold = max(threshold, self.best_offer_received)
                
                # Clamp threshold to valid range
                threshold = max(0, min(threshold, self.my_total))
                
                # Accept if current offer meets or exceeds threshold
                if current_offer_value >= threshold:
                    return None
        
        # Generate counter-offer
        # Calculate target value for ourselves
        progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
        # Start at 90%, decrease to 55% by the end
        target_fraction = 0.9 - 0.35 * progress
        
        # Don't target less than the best offer we've received (if decent)
        if self.best_offer_received >= 0.2 * self.my_total:
            target_fraction = max(target_fraction, self.best_offer_received / self.my_total)
        
        # Minimum target fractions based on remaining turns
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
            my_split = self._adjust_split(my_split, target_value)
            split_tuple = tuple(my_split)
            attempts += 1
        
        # Update tracking
        self.previous_offers.add(split_tuple)
        
        return my_split
    
    def _generate_split(self, target_value: float) -> list[int]:
        # Start with all items we value
        my_split = self.counts.copy()
        current_value = self.my_total
        
        # If we already meet or are below target, return
        if current_value <= target_value:
            return my_split
        
        # Determine which items to prioritize giving away
        give_priority = []
        if self.partner_offer_count > 0:
            # Sort items by:
            # 1. Higher partner keep ratio first (more they want it)
            # 2. Lower our value first (less we care about it)
            item_scores = []
            for i in range(len(self.counts)):
                if self.counts[i] == 0:
                    keep_ratio = 0.0
                else:
                    keep_ratio = self.partner_keep_counts[i] / (self.partner_offer_count * self.counts[i])
                # Use negative keep ratio so that higher ratios come first when sorted ascending
                # Use our value so lower values come first
                item_scores.append((-keep_ratio, self.values[i], i))
            item_scores.sort()
            give_priority = [i for (_, _, i) in item_scores]
        else:
            # Default: give least valuable items first
            give_priority = [i for (v, i) in self.sorted_items]
        
        # Give up items according to priority
        for idx in give_priority:
            if current_value <= target_value or self.values[idx] <= 0:
                continue
            
            available = my_split[idx]
            if available == 0:
                continue
            
            # Max number to give up to get as close as possible to target without going below
            max_give = min(available, int((current_value - target_value) // self.values[idx]))
            if max_give > 0:
                my_split[idx] -= max_give
                current_value -= max_give * self.values[idx]
            
            # If we can give up one more without going below a reasonable minimum, do it
            if current_value > target_value and my_split[idx] > 0:
                min_acceptable = max(0.2 * self.my_total, target_value - self.values[idx])
                if current_value - self.values[idx] >= min_acceptable:
                    my_split[idx] -= 1
                    current_value -= self.values[idx]
        
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
        # Find an item we can give up (least valuable first)
        for val, idx in self.sorted_items:
            if new_split[idx] > 0 and val > 0:
                # Find an item we can take instead (most valuable, same or lower value)
                for val2, idx2 in reversed(self.sorted_items):
                    if idx2 == idx:
                        continue
                    if new_split[idx2] < self.counts[idx2]:
                        # Check if this keeps us above target
                        new_val = current_value - val + val2
                        if new_val >= max(target_value, 0.2 * self.my_total):
                            new_split[idx] -= 1
                            new_split[idx2] += 1
                            return new_split
        
        # If all else fails, just take all positive value items and adjust
        return self._generate_split(target_value)