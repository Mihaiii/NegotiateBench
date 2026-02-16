class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_turns = 2 * max_rounds
        self.my_total = sum(c * v for c, v in zip(counts, values))
        # Precompute items with positive value sorted by ascending value (give up least valuable first)
        # Secondary sort by index for consistency
        self.sorted_items = sorted(
            [(v, i) for i, v in enumerate(values) if v > 0],
            key=lambda x: (x[0], x[1])
        )
        # Group indices by their value for swapping later
        self.value_groups = {}
        for i, v in enumerate(values):
            if v not in self.value_groups:
                self.value_groups[v] = []
            self.value_groups[v].append(i)
        self.turn_count = 0
        self.last_offer = None
        self.partner_offer_values = []
        self.my_offer_values = []

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Calculate actual turn number in the negotiation
        if self.me == 0:
            actual_turn = 2 * (self.turn_count - 1) + 1
        else:
            actual_turn = 2 * self.turn_count
        
        # Handle acceptance if we received an offer
        if o is not None:
            offer_value = sum(oi * vi for oi, vi in zip(o, self.values))
            self.partner_offer_values.append(offer_value)
            
            # Accept immediately if we value nothing or get everything
            if self.my_total == 0 or offer_value >= self.my_total:
                return None
            
            # Calculate acceptance threshold: linear from 90% to 50% except last turn
            remaining_turns = self.total_turns - actual_turn
            if actual_turn == self.total_turns:
                threshold = -1  # Accept anything (even 0) on last turn
            else:
                if self.total_turns == 1:
                    progress = 0.0
                else:
                    progress = (actual_turn - 1) / (self.total_turns - 1)
                threshold = self.my_total * (0.9 - 0.4 * progress)
            
            # Slight threshold reduction if partner is improving their offer
            if len(self.partner_offer_values) >= 2:
                if self.partner_offer_values[-1] > self.partner_offer_values[-2]:
                    threshold = max(0, threshold - 0.05 * self.my_total)
            
            # Check if we should accept
            if offer_value >= threshold:
                return None
        
        # Generate our counter-offer
        # Calculate progress and initial offer fraction
        if self.total_turns == 1:
            progress = 0.0
        else:
            progress = (actual_turn - 1) / (self.total_turns - 1)
        
        # Base fraction: 100% -> 55% over time
        offer_fraction = 1.0 - 0.45 * progress
        
        # Slow down concession if partner isn't improving
        if len(self.partner_offer_values) >= 2:
            if self.partner_offer_values[-1] <= self.partner_offer_values[-2]:
                # Only concede 1.5% max from our last offer
                if self.my_offer_values:
                    last_fraction = self.my_offer_values[-1] / self.my_total if self.my_total > 0 else 1.0
                    offer_fraction = max(offer_fraction, last_fraction - 0.015)
        
        # Ensure minimum 50% except for last 2 turns
        remaining_turns = self.total_turns - actual_turn
        if remaining_turns > 2:
            offer_fraction = max(offer_fraction, 0.5)
        
        offer_target = max(0, min(offer_fraction * self.my_total, self.my_total))
        
        # Start with maximum value split (take all valuable items)
        my_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(len(self.counts))]
        current_value = self.my_total
        
        # Adjust split to meet target by giving up least valuable items first, stay above target
        if current_value > offer_target and self.sorted_items:
            for val, idx in self.sorted_items:
                if current_value <= offer_target:
                    break
                available = my_split[idx]
                if available == 0:
                    continue
                
                # Calculate how many we can give up without going below target
                max_give = min(available, (current_value - offer_target) // val)
                if max_give > 0:
                    my_split[idx] -= max_give
                    current_value -= max_give * val
        
        # Avoid repeating the same offer as last time
        if self.last_offer is not None and my_split == self.last_offer:
            # First try to swap items of the same value to keep the same total
            swapped = False
            # Check all value groups with multiple items
            for v in self.value_groups:
                if len(self.value_groups[v]) < 2:
                    continue
                indices = self.value_groups[v]
                # Look for a pair to swap
                for i in range(len(indices)):
                    for j in range(len(indices)):
                        if i == j:
                            continue
                        idx_a = indices[i]  # We have some of this, can give up
                        idx_b = indices[j]  # Partner has some of this, can take
                        if my_split[idx_a] > 0 and (self.counts[idx_b] - my_split[idx_b]) > 0:
                            my_split[idx_a] -= 1
                            my_split[idx_b] += 1
                            # Value stays the same
                            swapped = True
                            break
                    if swapped:
                        break
                if swapped:
                    break
            # If no swap possible, give up one least valuable item (only if not too low)
            if not swapped and self.sorted_items:
                for val, idx in self.sorted_items:
                    if my_split[idx] > 0:
                        # Only do this if current value is still above 50% (or last 2 turns)
                        if remaining_turns <= 2 or current_value - val >= 0.5 * self.my_total:
                            my_split[idx] -= 1
                            current_value -= val
                        break
        
        # Update tracking variables
        self.last_offer = my_split.copy()
        self.my_offer_values.append(current_value)
        
        return my_split