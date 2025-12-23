class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.max_turns = max_rounds * 2  # Total number of turns
        self.turns_remaining = self.max_turns
        self.is_first = (me == 0)
        
        # Calculate our total value
        self.total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        
        # Sort items by our value per unit (descending)
        self.items_by_value = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
        
    def evaluate_offer(self, offer: list[int]) -> int:
        """Calculate the value of an offer according to our valuations."""
        return sum(self.values[i] * offer[i] for i in range(len(offer)))
    
    def create_offer(self, our_target_value: int) -> list[int]:
        """
        Create an offer that gives us approximately our_target_value.
        """
        offer = [0] * len(self.counts)
        current_value = 0
        
        # If total value is 0, any offer is acceptable
        if self.total_value == 0:
            return offer
        
        # Sort items by our value per unit (descending)
        for i in self.items_by_value:
            if current_value >= our_target_value:
                break
            
            # Skip items with 0 value to us
            if self.values[i] == 0:
                continue
            
            count = self.counts[i]
            item_value = self.values[i] * count
            
            if current_value + item_value <= our_target_value:
                offer[i] = count
                current_value += item_value
            else:
                needed = our_target_value - current_value
                offer[i] = needed // self.values[i]
                current_value += offer[i] * self.values[i]
        
        return offer
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        """Respond to an offer or make the first offer."""
        self.turns_remaining -= 1
        
        # If this is our first turn and we're first, make an initial offer
        if o is None:
            # If total value is 0, any offer is acceptable
            if self.total_value == 0:
                return [0] * len(self.counts)
            
            # Start by asking for a good share for ourselves
            return self.create_offer(int(self.total_value * 0.8))
        
        # Evaluate the partner's offer
        offer_value = self.evaluate_offer(o)
        
        # If total value is 0, any offer is acceptable
        if self.total_value == 0:
            return None
        
        # Calculate the minimum acceptable value based on remaining turns
        # As turns decrease, we become more willing to accept lower offers
        turns_remaining_ratio = self.turns_remaining / self.max_turns
        min_acceptable = int(self.total_value * (0.5 + 0.3 * turns_remaining_ratio))
        
        # Accept if the offer is good enough
        if offer_value >= min_acceptable:
            return None
        
        # If this is the last turn, we need to accept whatever is offered
        if self.turns_remaining == 0:
            return None
        
        # Otherwise, make a counter-offer
        # Adjust our target value based on how many turns remain
        target_value = int(self.total_value * (0.7 - 0.2 * (1 - turns_remaining_ratio)))
        return self.create_offer(target_value)