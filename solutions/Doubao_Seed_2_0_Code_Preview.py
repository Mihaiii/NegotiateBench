class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_turns = 2 * max_rounds
        self.my_total = sum(c * v for c, v in zip(counts, values))
        # Sort items with positive value by ascending value (give up least valuable first)
        self.sorted_items = sorted(
            [(v, i) for i, v in enumerate(values) if v > 0],
            key=lambda x: (x[0], x[1])
        )
        self.turn_count = 0
        self.previous_my_offers = set()
        self.partner_offer_values = []
        self.my_offer_values = []

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
        if o is not None:
            # Validate offer
            valid = True
            for i in range(len(o)):
                if not isinstance(o[i], int) or o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
            if valid:
                current_offer_value = sum(oi * vi for oi, vi in zip(o, self.values))
                self.partner_offer_values.append(current_offer_value)
                
                # Acceptance checks
                if current_offer_value >= self.my_total:
                    return None  # Accept if we get everything
                
                if actual_turn == self.total_turns:
                    # Accept only if better than nothing
                    if current_offer_value > 0:
                        return None
                    else:
                        # Reject, since same as nothing
                        pass
                else:
                    # Calculate threshold
                    progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
                    base_threshold = self.my_total * (0.9 - 0.4 * progress)
                    threshold = base_threshold
                    
                    # Adjust threshold based on partner behavior
                    if len(self.partner_offer_values) >= 2:
                        if self.partner_offer_values[-1] > self.partner_offer_values[-2]:
                            # Partner is improving, lower threshold slightly
                            threshold = max(0.5 * self.my_total, threshold - 0.05 * self.my_total)
                        elif self.partner_offer_values[-1] <= self.partner_offer_values[-2]:
                            # Partner is not improving, keep threshold higher
                            threshold = min(threshold + 0.05 * self.my_total, 0.95 * self.my_total)
                    
                    # Ensure minimum threshold when there are enough turns left
                    if remaining_turns > 2:
                        threshold = max(threshold, 0.5 * self.my_total)
                    
                    # Clamp threshold to valid range
                    threshold = max(0.0, min(threshold, self.my_total))
                    
                    if current_offer_value >= threshold:
                        return None
        
        # Generate counter-offer
        progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
        target_fraction = 1.0 - 0.4 * progress  # Gradually reduce from 100% to 60%
        
        # Adjust target based on partner behavior
        if len(self.partner_offer_values) >= 2:
            if self.partner_offer_values[-1] <= self.partner_offer_values[-2]:
                # Partner not improving, hold ground
                if self.my_offer_values:
                    last_my_fraction = self.my_offer_values[-1] / self.my_total
                    target_fraction = max(target_fraction, last_my_fraction - 0.02)
        
        # Ensure minimum target fraction
        min_fraction = 0.5 if remaining_turns > 2 else 0.3
        target_fraction = max(target_fraction, min_fraction)
        target_fraction = min(target_fraction, 1.0)
        
        target_value = target_fraction * self.my_total
        target_value = max(0, min(target_value, self.my_total))
        
        # Generate split: start with all positive value items
        my_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(len(self.counts))]
        current_value = self.my_total
        
        # Adjust to meet target by giving up least valuable items first
        if current_value > target_value and self.sorted_items:
            for val, idx in self.sorted_items:
                if current_value <= target_value:
                    break
                available = my_split[idx]
                if available == 0:
                    continue
                # Calculate how many to give up
                max_give = min(available, int((current_value - target_value) // val))
                if max_give > 0:
                    my_split[idx] -= max_give
                    current_value -= max_give * val
            # If still above target, give up one more if possible
            if current_value > target_value and self.sorted_items:
                for val, idx in self.sorted_items:
                    if my_split[idx] > 0:
                        new_val = current_value - val
                        if new_val >= 0.3 * self.my_total or remaining_turns <= 2:
                            my_split[idx] -= 1
                            current_value = new_val
                            break
        
        # Avoid repeating offers
        split_tuple = tuple(my_split)
        if split_tuple in self.previous_my_offers:
            modified = False
            # First try adjusting zero-value items
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    if my_split[i] < self.counts[i]:
                        my_split[i] += 1
                        new_tuple = tuple(my_split)
                        if new_tuple not in self.previous_my_offers:
                            modified = True
                            break
                        my_split[i] -= 1
                    if my_split[i] > 0:
                        my_split[i] -= 1
                        new_tuple = tuple(my_split)
                        if new_tuple not in self.previous_my_offers:
                            modified = True
                            break
                        my_split[i] += 1
            if modified:
                split_tuple = tuple(my_split)
            else:
                # Try swapping same value items
                value_groups = {}
                for i, v in enumerate(self.values):
                    if v not in value_groups:
                        value_groups[v] = []
                    value_groups[v].append(i)
                for v in value_groups:
                    if len(value_groups[v]) < 2:
                        continue
                    indices = value_groups[v]
                    for i in range(len(indices)):
                        for j in range(len(indices)):
                            if i == j:
                                continue
                            idx_a, idx_b = indices[i], indices[j]
                            if my_split[idx_a] > 0 and (self.counts[idx_b] - my_split[idx_b]) > 0:
                                my_split[idx_a] -= 1
                                my_split[idx_b] += 1
                                modified = True
                                break
                        if modified:
                            break
                    if modified:
                        break
                if modified:
                    split_tuple = tuple(my_split)
                else:
                    # If no swap, give up one least valuable if possible
                    if self.sorted_items:
                        for val, idx in self.sorted_items:
                            if my_split[idx] > 0:
                                new_value = current_value - val
                                if remaining_turns <= 2 or new_value >= 0.3 * self.my_total:
                                    my_split[idx] -= 1
                                    current_value = new_value
                                    split_tuple = tuple(my_split)
                                    break
        
        # Ensure valid split
        my_split = [int(x) for x in my_split]
        valid = True
        for i in range(len(my_split)):
            if my_split[i] < 0 or my_split[i] > self.counts[i]:
                valid = False
                break
        if not valid:
            # Fallback to simple split
            my_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(len(self.counts))]
            current_value = self.my_total
            split_tuple = tuple(my_split)
        
        # Update tracking
        self.previous_my_offers.add(split_tuple)
        self.my_offer_values.append(current_value)
        
        return my_split