class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_turns = 2 * max_rounds
        self.my_total = sum(c * v for c, v in zip(counts, values))
        # Precompute items with positive value sorted by ascending value (give up least valuable first)
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
        self.partner_offer_values = []
        self.my_offer_values = []
        self.best_partner_offer = -1
        self.previous_my_offers = set()

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Calculate actual turn number in the negotiation
        if self.me == 0:
            actual_turn = 2 * (self.turn_count - 1) + 1
        else:
            actual_turn = 2 * self.turn_count
        
        remaining_turns = self.total_turns - actual_turn
        
        # Handle acceptance if we received an offer
        if o is not None:
            # Validate offer first
            valid = True
            for i in range(len(o)):
                if not isinstance(o[i], int) or o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
            if not valid:
                # Invalid offer, walk away? Wait no, better to counter, but let's just not accept
                pass
            else:
                offer_value = sum(oi * vi for oi, vi in zip(o, self.values))
                self.partner_offer_values.append(offer_value)
                
                # Update best partner offer
                if offer_value > self.best_partner_offer:
                    self.best_partner_offer = offer_value
                
                # Accept immediately if we value nothing or get everything
                if self.my_total == 0 or offer_value >= self.my_total:
                    return None
                
                # Calculate acceptance threshold
                if actual_turn == self.total_turns:
                    threshold = 0  # Accept anything non-negative on last turn
                else:
                    progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
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
        progress = (actual_turn - 1) / (self.total_turns - 1) if self.total_turns > 1 else 0.0
        
        # Base fraction: 100% -> 55% over time
        offer_fraction = 1.0 - 0.45 * progress
        
        # Ensure we don't ask for more than our last offer
        if self.my_offer_values:
            last_offer_value = self.my_offer_values[-1]
            max_offer_target = last_offer_value
        else:
            max_offer_target = self.my_total
        
        offer_target = min(offer_fraction * self.my_total, max_offer_target)
        
        # Slow down concession if partner isn't improving
        if len(self.partner_offer_values) >= 2:
            if self.partner_offer_values[-1] <= self.partner_offer_values[-2]:
                if self.my_offer_values:
                    last_fraction = self.my_offer_values[-1] / self.my_total if self.my_total > 0 else 1.0
                    offer_fraction = max(offer_fraction, last_fraction - 0.015)
                    offer_target = min(offer_fraction * self.my_total, max_offer_target)
        
        # Ensure minimum 50% except for last 2 turns
        if remaining_turns > 2:
            offer_target = max(offer_target, 0.5 * self.my_total)
        
        offer_target = max(0, min(offer_target, self.my_total))
        
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
                
                # Calculate how many we can give up without going below target (ensure integer)
                max_give = min(available, int((current_value - offer_target) // val))
                if max_give > 0:
                    my_split[idx] -= max_give
                    current_value -= max_give * val
        
        # Avoid repeating any previous offer
        my_split_tuple = tuple(my_split)
        if my_split_tuple in self.previous_my_offers:
            # First try to swap items of the same value to keep the same total
            swapped = False
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
                        new_value = current_value - val
                        if remaining_turns <= 2 or new_value >= 0.5 * self.my_total:
                            my_split[idx] -= 1
                            current_value = new_value
                            break
        
        # Ensure all elements are integers
        my_split = [int(x) for x in my_split]
        
        # Update tracking variables
        final_tuple = tuple(my_split)
        self.previous_my_offers.add(final_tuple)
        self.my_offer_values.append(current_value)
        
        return my_split