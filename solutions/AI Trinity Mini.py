class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total_value = sum(values)
        self.threshold = self.total_value / 2
        self.rounds_left = max_rounds * 2  # Convert rounds to turns
        self.my_offers = []
        self.partner_offers = []
        self.my_util = 0
        self.partner_util = 0
        self.my_offers.append([0] * len(counts))
        self.partner_offers.append([0] * len(counts))
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is None:
            # First turn: make initial offer
            offer = self._generate_initial_offer()
            self.rounds_left -= 1
            return offer
        
        # Update partner's offer and calculate their utility
        self.partner_offers.append(o)
        self.partner_util += sum(o[i] * self.values[i] for i in range(len(self.values)))
        
        # Calculate my utility from current offer
        my_util = sum(o[i] * self.values[i] for i in range(len(self.values)))
        self.my_offers.append(o)
        
        # Check if offer is acceptable
        if my_util >= self.threshold:
            self.rounds_left -= 1
            return None  # Accept
        
        # Generate counter-offer
        counter_offer = self._generate_counter_offer()
        self.rounds_left -= 1
        return counter_offer
    
    def _generate_initial_offer(self) -> list[int]:
        # Start with all items for me
        offer = self.counts.copy()
        # Adjust to leave some items for partner if needed
        if sum(offer) > 0:
            offer = [0] * len(self.counts)
        return offer
    
    def _generate_counter_offer(self) -> list[int]:
        # Sort items by value descending
        sorted_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        # Start with current offer
        offer = self.my_offers[-1].copy()
        current_util = sum(offer[i] * self.values[i] for i in range(len(self.values)))
        
        # Try to improve utility
        for i in sorted_indices:
            # Skip items already fully allocated
            if offer[i] == self.counts[i]:
                continue
            # Calculate potential utility gain
            gain = self.values[i]
            # Check if we can improve without exceeding threshold
            if current_util + gain >= self.threshold:
                # Allocate remaining items of this type
                remaining = self.counts[i] - offer[i]
                offer[i] += remaining
                current_util += gain * remaining
                break
            else:
                # Allocate one item of this type
                offer[i] += 1
                current_util += gain
                if current_util >= self.threshold:
                    break
        
        return offer