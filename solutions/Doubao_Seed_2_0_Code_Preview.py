class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_turns = 2 * max_rounds
        self.my_total = sum(c * v for c, v in zip(counts, values))
        
        # Sort items by our value ascending (least valuable to us first)
        self.sorted_items = sorted(
            [(v, i) for i, v in enumerate(values)],
            key=lambda x: (x[0], x[1])
        )
        
        self.turn_count = 0
        self.best_offer_value = 0  # Best value we've been offered
        self.best_offer_split = None  # The actual split that gave best value
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
        valid_offer = False
        if o is not None:
            # Validate offer first
            valid_offer = True
            for i in range(len(o)):
                if not isinstance(o[i], int) or o[i] < 0 or o[i] > self.counts[i]:
                    valid_offer = False
                    break
            
            if valid_offer:
                current_offer_value = sum(oi * vi for oi, vi in zip(o, self.values))
                
                # Update best offer received
                if current_offer_value > self.best_offer_value:
                    self.best_offer_value = current_offer_value
                    self.best_offer_split = o.copy()
                
                # Update partner tracking (partner keeps counts[i] - o[i])
                self.partner_offer_count += 1
                for i in range(len(o)):
                    self.partner_keep_counts[i] += (self.counts[i] - o[i])
                
                # Acceptance checks
                # 1. If we get everything, accept immediately
                if current_offer_value >= self.my_total:
                    return None
                
                # 2. If it's the last turn, accept anything better than 0
                if actual_turn == self.total_turns:
                    if current_offer_value > 0:
                        return None
                
                # Calculate dynamic acceptance threshold
                progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
                # Start at 70%, decrease to 50% by the end
                threshold_fraction = 0.7 - 0.2 * progress
                # Never go below 40% except on last turn
                if actual_turn != self.total_turns:
                    threshold_fraction = max(threshold_fraction, 0.4)
                threshold = self.my_total * threshold_fraction
                
                # Never go below the best offer we've received (but at least 0)
                threshold = max(threshold, self.best_offer_value, 0)
                
                # Accept if current offer meets or exceeds threshold
                if current_offer_value >= threshold - 1e-9:  # Account for floating point errors
                    return None
        
        # Generate counter-offer
        # Calculate target value for ourselves
        progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
        # Start at 75%, decrease to 50% by the end
        target_fraction = 0.75 - 0.25 * progress
        
        # Don't target less than the best offer we've received (if it's meaningful)
        if self.best_offer_value > 0.2 * self.my_total:
            target_fraction = max(target_fraction, self.best_offer_value / self.my_total)
        
        # Ensure target fraction is within valid range
        target_fraction = max(0.5, min(target_fraction, 1.0))
        target_value = target_fraction * self.my_total
        
        # Generate the split
        my_split = self._generate_split(target_value)
        
        # Make sure we don't repeat offers
        split_tuple = tuple(my_split)
        attempts = 0
        while split_tuple in self.previous_offers and attempts < 50:
            my_split = self._adjust_split(my_split, target_value)
            split_tuple = tuple(my_split)
            attempts += 1
        
        # Update tracking
        self.previous_offers.add(split_tuple)
        
        return my_split
    
    def _generate_split(self, target_value: float) -> list[int]:
        # Start with all items
        my_split = self.counts.copy()
        current_value = self.my_total
        
        # If we're already at or below target, return
        if current_value <= target_value + 1e-9:
            return my_split
        
        # Determine priority of items to give away
        give_priority = self._get_give_priority()
        
        # Give up items according to priority
        for idx in give_priority:
            if current_value <= target_value + 1e-9:
                break
            if self.values[idx] <= 0:
                # Give away all worthless items first
                give = my_split[idx]
                my_split[idx] -= give
                current_value -= give * self.values[idx]
                continue
            
            available = my_split[idx]
            if available == 0:
                continue
            
            # Calculate how many to give up to get close to target
            value_per_item = self.values[idx]
            max_possible_give = min(available, int((current_value - target_value) // value_per_item))
            if max_possible_give > 0:
                my_split[idx] -= max_possible_give
                current_value -= max_possible_give * value_per_item
            
            # Check if we can give one more without going below a minimum
            if current_value > target_value + 1e-9 and my_split[idx] > 0:
                min_acceptable = max(0.5 * self.my_total, target_value - value_per_item)
                if current_value - value_per_item >= min_acceptable - 1e-9:
                    my_split[idx] -= 1
                    current_value -= value_per_item
        
        return my_split
    
    def _get_give_priority(self) -> list[int]:
        # Calculate partner's keep ratio for each item
        partner_ratios = []
        for i in range(len(self.counts)):
            if self.partner_offer_count == 0 or self.counts[i] == 0:
                ratio = 0.0
            else:
                ratio = self.partner_keep_counts[i] / (self.partner_offer_count * self.counts[i])
            partner_ratios.append((ratio, i))
        
        # Sort items into priority for giving away:
        # 1. First, items with our value 0, sorted by partner ratio descending
        # 2. Then, items with our value >0, sorted by (partner ratio descending, our value ascending)
        zero_val = []
        positive_val = []
        for ratio, i in partner_ratios:
            if self.values[i] == 0:
                zero_val.append((-ratio, i))  # Negative for ascending sort = higher ratio first
            else:
                positive_val.append((-ratio, self.values[i], i))
        
        # Sort the lists
        zero_val.sort()
        positive_val.sort()
        
        # Combine into priority list
        priority = [i for (_, i) in zero_val] + [i for (_, _, i) in positive_val]
        return priority
    
    def _adjust_split(self, current_split: list[int], target_value: float) -> list[int]:
        new_split = current_split.copy()
        current_value = sum(mi * vi for mi, vi in zip(new_split, self.values))
        min_acceptable = max(target_value, 0.5 * self.my_total)
        
        # First, try swapping items of the same value to get a new split
        value_groups = {}
        for i, v in enumerate(self.values):
            if v not in value_groups:
                value_groups[v] = []
            value_groups[v].append(i)
        
        for v in value_groups:
            indices = value_groups[v]
            if len(indices) < 2:
                continue
            # Try all pairs in the same value group
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    a, b = indices[i], indices[j]
                    # Take one from a, give to b
                    if new_split[a] > 0 and new_split[b] < self.counts[b]:
                        new_split[a] -= 1
                        new_split[b] += 1
                        return new_split
                    # Take one from b, give to a
                    if new_split[b] > 0 and new_split[a] < self.counts[a]:
                        new_split[b] -= 1
                        new_split[a] += 1
                        return new_split
        
        # Next, try giving up a low-value item and taking a zero-value item
        zero_indices = [i for i, v in enumerate(self.values) if v == 0]
        # Iterate over our items from least to most valuable
        for val, idx in self.sorted_items:
            if val <= 0 or new_split[idx] == 0:
                continue
            # Try to take a zero-value item instead
            for z_idx in zero_indices:
                if new_split[z_idx] < self.counts[z_idx]:
                    new_split[idx] -= 1
                    new_split[z_idx] += 1
                    # Check if we're still above min acceptable
                    new_val = current_value - val
                    if new_val >= min_acceptable - 1e-9:
                        return new_split
                    # Revert if not
                    new_split[idx] += 1
                    new_split[z_idx] -= 1
        
        # Try small adjustments: give up one, take another (higher or equal value)
        for val_give, idx_give in self.sorted_items:
            if val_give <= 0 or new_split[idx_give] == 0:
                continue
            # Look for items to take (sorted by value descending)
            for val_take, idx_take in reversed(self.sorted_items):
                if idx_take == idx_give:
                    continue
                if new_split[idx_take] >= self.counts[idx_take]:
                    continue
                # Calculate new value
                new_val = current_value - val_give + val_take
                if new_val >= min_acceptable - 1e-9:
                    new_split[idx_give] -= 1
                    new_split[idx_take] += 1
                    return new_split
        
        # If all else fails, generate a split with slightly lower target
        lower_target = max(target_value - 0.05 * self.my_total, 0.5 * self.my_total)
        return self._generate_split(lower_target)