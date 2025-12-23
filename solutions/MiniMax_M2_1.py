class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total = sum(counts[i] * values[i] for i in range(len(counts)))
        self.total_turns = 2 * max_rounds
        self.turns = 0
        self.min_acceptable = self.total * 0.35  # Accept at least 35% of total value
        self.best_offer = None
        self.best_offer_value = 0
        self.offered_items = counts[:]  # Track what we initially demand
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turns += 1
        remaining_turns = self.total_turns - self.turns
        
        # If partner made an offer, evaluate it
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Track best offer received
            if offered_value > self.best_offer_value:
                self.best_offer = o[:]
                self.best_offer_value = offered_value
            
            # Accept if it's good enough
            if offered_value >= self.min_acceptable:
                return None
            
            # Calculate our fallback demand based on remaining time
            concession_rate = remaining_turns / self.total_turns
            target_value = self.min_acceptable + (self.total - self.min_acceptable) * concession_rate
            
            # Build a strategic counter-offer
            counter = [0] * len(self.counts)
            remaining_items = self.counts[:]
            
            # First, try to get items we value most that partner might not want
            # Sort items by value ratio (high value to us, hopefully low to partner)
            item_indices = list(range(len(self.counts)))
            item_indices.sort(key=lambda i: -self.values[i])
            
            for i in item_indices:
                if self.values[i] > 0 and remaining_items[i] > 0:
                    # Calculate how much value this item gives us
                    item_value = self.values[i]
                    
                    # If we still need more value, take this item
                    if sum(counter[j] * self.values[j] for j in range(len(counter))) < target_value:
                        counter[i] = 1
                        remaining_items[i] -= 1
            
            # If we haven't reached target value, add more items
            for i in item_indices:
                while remaining_items[i] > 0 and sum(counter[j] * self.values[j] for j in range(len(counter))) < target_value:
                    counter[i] += 1
                    remaining_items[i] -= 1
            
            return counter
        
        # First turn or no offer to respond to
        # Make initial demand: ask for everything we value
        initial_demand = [0] * len(self.counts)
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                initial_demand[i] = self.counts[i]
        
        return initial_demand