class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.turn = 0
        self.total = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        self.opponent_offers = []
    
    def value_of(self, offer):
        if offer is None:
            return 0
        return sum(offer[i] * self.values[i] for i in range(self.n))
    
    def infer_opponent_values(self):
        """Infer opponent's likely low-value items from their offers."""
        if not self.opponent_offers:
            return set()
        
        # Items consistently offered to me are likely low-value to opponent
        low_value_items = set()
        last_offer = self.opponent_offers[-1]
        for i in range(self.n):
            if last_offer[i] == self.counts[i]:  # They offered me all of this item
                low_value_items.add(i)
        return low_value_items
    
    def offer(self, o):
        self.turn += 1
        remaining = self.max_rounds - self.turn
        
        if o is not None:
            self.opponent_offers.append(o)
            my_val = self.value_of(o)
            
            # Player 1's last turn: must accept anything
            if self.me == 1 and remaining == 0:
                return None
            
            # Calculate acceptance threshold based on game position
            if remaining == 0:
                # Player 0's last turn - can counter greedily
                threshold = self.total * 0.1
            elif self.me == 0:
                # Player 0 has penultimate move advantage
                threshold = self.total * 0.35
            else:
                # Player 1 should be more accepting
                threshold = self.total * 0.30
            
            # Reduce threshold as rounds progress
            threshold *= 0.85 ** remaining
            
            if my_val >= threshold:
                return None
        
        # Make counter-offer
        # Player 0's last turn: make greedy offer
        if self.me == 0 and remaining == 0:
            return [c if v > 0 else 0 for c, v in zip(self.counts, self.values)]
        
        # Otherwise: make a balanced offer
        return self.make_balanced_offer()
    
    def make_balanced_offer(self):
        """Create an offer targeting ~55-60% of total value."""
        offer = [0] * self.n
        target = self.total * 0.58
        current_val = 0
        
        # Get hints about opponent's preferences
        opponent_low_value = self.infer_opponent_values()
        
        # Sort items by my value (descending), but prioritize items opponent might not want
        def sort_key(i):
            # Higher priority if opponent offered it to me (they likely don't value it)
            priority_boost = 10 if i in opponent_low_value else 0
            return (priority_boost + self.values[i], self.values[i])
        
        sorted_items = sorted(range(self.n), key=sort_key, reverse=True)
        
        for i in sorted_items:
            if self.values[i] == 0:
                # I don't value it - give all to opponent
                offer[i] = 0
            elif current_val < target:
                take = self.counts[i]
                potential_val = current_val + take * self.values[i]
                
                # Don't take too much over target
                if potential_val > target + self.values[i] * 0.5:
                    needed = target - current_val
                    if self.values[i] > 0:
                        take = max(1, int(needed / self.values[i]))
                
                offer[i] = min(take, self.counts[i])
                current_val += offer[i] * self.values[i]
            else:
                # Already met target, give rest to opponent
                offer[i] = 0
        
        return offer