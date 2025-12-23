class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total_rounds = max_rounds
        self.rounds_left = max_rounds
        self.total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        self.sorted_indices = sorted(range(len(counts)), key=lambda i: -values[i])
        self.offers_received = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_left -= 1
        
        # First turn: make initial strategic demand
        if o is None:
            # Strategic opening: demand all high-value items but leave partner something
            target = self.total_value * 0.55  # Reasonable opening demand
            return self._build_demand(target)
        
        # Analyze partner's offer
        offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
        self.offers_received.append(o)
        
        # Calculate fair share threshold - becomes more flexible as time passes
        fair_share = self.total_value * 0.5
        pressure_factor = 1.0 - (self.rounds_left / self.total_rounds) * 0.3
        min_acceptable = fair_share * pressure_factor
        
        # Accept if offer meets minimum threshold
        if offered_value >= min_acceptable:
            return None
            
        # Last chance: accept any positive offer to avoid getting nothing
        if self.rounds_left == 0:
            return None
            
        # Build counter-offer using strategic calculation
        # Partner's revealed value gives us insight into what they might accept
        partner_revealed_value = self._estimate_partner_value(o)
        
        # Calculate strategic counter - leave partner enough to make deal attractive
        # but maximize our share
        my_share_target = max(min_acceptable + 1, self.total_value * 0.52)
        
        # Make smaller concessions as rounds progress
        concession = (self.rounds_left / self.total_rounds) * 0.1
        counter_target = self.total_value * (0.5 + concession)
        
        counter = self._build_counter_offer(counter_target)
        
        # Verify counter is valid (sums to available items)
        if sum(counter) > sum(self.counts):
            counter = self._build_counter_offer(counter_target * 0.9)
            
        return counter
    
    def _estimate_partner_value(self, offer: list[int]) -> float:
        """Estimate partner's total valuation based on their offer patterns."""
        if not offer:
            return self.total_value
            
        # Partner is offering us 'offer', so they keep the rest
        # Their share is: total_value - value_of_offer_to_us
        offer_value_to_me = sum(offer[i] * self.values[i] for i in range(len(offer)))
        
        # But we don't know their values, so estimate conservatively
        # If they offer us low-value items, they probably value those items less
        min_possible_value = 0
        
        # Assume partner values items at least something if they're offering them
        for i in range(len(offer)):
            if offer[i] < self.counts[i] and offer[i] > 0:
                # They're keeping some, so they value it at least something
                if self.values[i] > 0:
                    min_possible_value += (self.counts[i] - offer[i]) * 1
        
        return max(min_possible_value, self.total_value * 0.3)
    
    def _build_demand(self, target_value: float) -> list[int]:
        """Build initial demand focusing on high-value items."""
        return self._build_counter_offer(target_value)
    
    def _build_counter_offer(self, target_value: float) -> list[int]:
        """Build counter-offer targeting specific value."""
        counter = [0] * len(self.counts)
        remaining = self.counts[:]
        current_value = 0
        
        # First pass: take all high-value items we strongly prefer
        for i in self.sorted_indices:
            if remaining[i] > 0 and self.values[i] > 0:
                item_value = self.values[i]
                # Take all if it's one of our top priorities
                if item_value >= max(self.values) * 0.8:
                    take = min(remaining[i], 1)  # Take at most 1 of top items
                    counter[i] = take
                    remaining[i] -= take
                    current_value += take * item_value
        
        # Second pass: strategically fill to reach target
        for i in self.sorted_indices:
            if remaining[i] > 0 and current_value < target_value:
                item_value = self.values[i]
                if item_value > 0:
                    needed = max(0, int((target_value - current_value + item_value - 1) / item_value))
                    take = min(remaining[i], needed)
                    if take > 0:
                        counter[i] = take
                        remaining[i] -= take
                        current_value += take * item_value
        
        # Third pass: add more items if we have room and partner would likely accept
        for i in self.sorted_indices:
            if remaining[i] > 0:
                counter[i] += 1
                remaining[i] -= 1
                break  # Just add one more item to make deal more attractive
        
        return counter