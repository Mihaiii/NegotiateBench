class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_elapsed = 0
        
        # Calculate total value
        self.total_value = sum(count * value for count, value in zip(counts, values))
        
        # Store opponent's offer history to try to infer their preferences
        self.opponent_history = []
        self.my_history = []
        
        # Calculate threshold percentages that get more strict as time runs out
        self.acceptance_threshold = 0.7  # Start high then decrease

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_elapsed += 1
        current_turn = self.rounds_elapsed * 2 - (1 if self.me == 0 else 0)  # Adjust based on whether I'm first or second
        
        # If it's the opponent's offer (not the first turn)
        if o is not None:
            # Evaluate the offer and decide whether to accept
            
            # Calculate value of the offered items for me
            my_value_from_offer = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Calculate percentage of total value this represents
            percentage_of_total = my_value_from_offer / self.total_value if self.total_value > 0 else 0
            
            # As rounds go on, lower our acceptance threshold to ensure agreement
            current_threshold = self.acceptance_threshold * (1 - ((self.rounds_elapsed - 1) / self.max_rounds) * 0.4)  # Threshold decreases
            
            # Add to opponent history to track their offers
            self.opponent_history.append(o)
            
            # If the offer is good enough relative to our threshold or if we're running out of time, accept
            if percentage_of_total >= current_threshold or self.rounds_elapsed >= self.max_rounds:
                return None  # Accept the offer
        
        # Make a counter-offer if we rejected
        # Start with what we want most based on value
        my_request = [0] * len(self.counts)
        
        # Calculate priority by value and assign items strategically
        # Items with highest value get priority, but make sure to leave something for opponent
        item_priorities = [(self.values[i], i) for i in range(len(self.values))]
        item_priorities.sort(reverse=True)  # Most valuable items first
        
        remaining_counts = self.counts[:]
        
        # Get maximum possible value items first, but be willing to compromise
        # Adjust request based on opponent's previous preferences if known
        for _, idx in item_priorities:
            if self.values[idx] > 0:
                # Calculate how many of this item are available
                available = remaining_counts[idx]
                my_request[idx] = available
                remaining_counts[idx] = 0
            else:
                my_request[idx] = 0
        
        # Check if this is a reasonable offer - not everything to me if I can avoid it
        my_valuation = sum(my_request[i] * self.values[i] for i in range(len(my_request)))
        
        # If I'm asking for everything or almost everything, maybe adjust to be more collaborative
        # especially in early rounds to encourage negotiation
        opponent_gets_something = sum((self.counts[i] - my_request[i]) for i in range(len(self.counts)) if self.counts[i] - my_request[i] > 0) > 0
        
        if my_valuation >= self.total_value * 0.9 and self.rounds_elapsed < self.max_rounds and not opponent_gets_something:
            # Be more collaborative - ensure opponent gets something
            for i in range(len(my_request)):
                if my_request[i] > 0 and self.values[i] == min(v for v in self.values if v > 0):
                    # Offer at least one less valuable item to opponent
                    if my_request[i] > 0:
                        my_request[i] -= 1
                        break
        
        # Make sure we're not requesting more than available
        for i in range(len(my_request)):
            my_request[i] = min(my_request[i], self.counts[i])
        
        return my_request