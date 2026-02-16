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
            key=lambda x: x[0]
        )
        self.turn_count = 0
        self.last_offer = None
        self.partner_offers = []

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Calculate actual turn number in the negotiation
        if self.me == 0:
            actual_turn = 2 * (self.turn_count - 1) + 1
        else:
            actual_turn = 2 * self.turn_count
        
        # Handle acceptance if we received an offer
        if o is not None:
            self.partner_offers.append(o.copy())
            offer_value = sum(oi * vi for oi, vi in zip(o, self.values))
            
            # Accept immediately if we value nothing
            if self.my_total == 0:
                return None
            
            # Calculate base threshold: linear decrease from 90% to 0%
            if self.total_turns == 1:
                fraction = 1.0
            else:
                fraction = (actual_turn - 1) / (self.total_turns - 1)
            threshold = self.my_total * (0.9 - 0.9 * fraction)
            
            # Adjust threshold based on partner's concessions
            if len(self.partner_offers) >= 2:
                prev_offer = self.partner_offers[-2]
                curr_offer = self.partner_offers[-1]
                prev_value = sum(oi * vi for oi, vi in zip(prev_offer, self.values))
                curr_value = sum(oi * vi for oi, vi in zip(curr_offer, self.values))
                # Lower threshold if partner made a better offer to us
                if curr_value > prev_value:
                    threshold = max(0, threshold - 0.1 * self.my_total)
            
            # Accept any non-negative offer on the last turn
            if actual_turn == self.total_turns:
                threshold = -1
            
            # Ensure threshold is not negative except for last turn
            if actual_turn != self.total_turns:
                threshold = max(0, threshold)
            
            if offer_value >= threshold:
                return None
        
        # Generate our counter-offer
        # Calculate target value: linear decrease from 100% to 40%
        if self.total_turns == 1:
            offer_fraction = 0.5
        else:
            progress = (actual_turn - 1) / (self.total_turns - 1)
            offer_fraction = 1.0 - 0.6 * progress  # 100% -> 40%
        offer_target = max(0, min(offer_fraction * self.my_total, self.my_total))
        
        # Start with maximum value split (take all valuable items)
        my_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(len(self.counts))]
        current_value = self.my_total
        
        # Adjust split to meet target by giving up least valuable items first
        if current_value > offer_target and self.sorted_items:
            need_to_give = current_value - offer_target
            for val, idx in self.sorted_items:
                if need_to_give <= 0:
                    break
                available = my_split[idx]
                if available == 0:
                    continue
                
                # Give as many as possible without exceeding need_to_give
                max_possible = min(available, int(need_to_give // val))
                if max_possible > 0:
                    my_split[idx] -= max_possible
                    current_value -= max_possible * val
                    need_to_give -= max_possible * val
                
                # Give one more if still needed (even if slightly under target)
                if need_to_give > 0 and my_split[idx] > 0:
                    my_split[idx] -= 1
                    current_value -= val
                    need_to_give -= val
        
        # Avoid repeating the same offer as last time
        if self.last_offer is not None and my_split == self.last_offer and self.sorted_items:
            for val, idx in self.sorted_items:
                if my_split[idx] > 0:
                    my_split[idx] -= 1
                    current_value -= val
                    break
        
        # Update last offer and return
        self.last_offer = my_split.copy()
        return my_split