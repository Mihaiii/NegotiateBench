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
        
        # Variables for dynamic negotiation strategy
        self.concession_rate = 1.0  # Start optimistic, become more concessive as rounds pass
        self.min_acceptable_ratio = 0.4  # Lowest acceptable ratio of total value
        self.best_offer_seen = 0  # Track best offer we could accept so far

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_elapsed += 1
        
        # If opponent made an offer
        if o is not None:
            # Calculate value of the offered items for me
            my_value_from_offer = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Update history
            if self.opponent_history and self.opponent_history[-1] == o:
                # If the same offer is repeated, consider becoming more flexible
                # because opponent might be inflexible
                self.min_acceptable_ratio = max(0.3, self.min_acceptable_ratio - 0.05)
            
            # Add to opponent history
            self.opponent_history.append(o)
            
            # Calculate how much of total value I'm getting
            percentage_of_total = my_value_from_offer / self.total_value if self.total_value > 0 else 0
            
            # Dynamic acceptance based on:
            # 1. How generous the offer is
            # 2. How many rounds remain
            # 3. Whether we're making progress
            current_threshold = self.min_acceptable_ratio
            
            # Increase acceptance willingness as we get closer to the deadline
            if self.max_rounds > 0:
                remaining_ratio = (self.max_rounds - self.rounds_elapsed) / self.max_rounds
                # If we have very few rounds left, lower our standards
                if remaining_ratio < 0.2:  # In final 20% of rounds
                    current_threshold =	max(0.1, current_threshold * 0.5)
                elif remaining_ratio < 0.4:
                    current_threshold = max(0.2, current_threshold * 0.75)
            
            # Check if this offer contains more than the threshold
            if percentage_of_total >= current_threshold:
                # Consider if it's worth holding out for a better offer
                if self.max_rounds <= self.rounds_elapsed or percentage_of_total > 0.7 or len(self.opponent_history) <= 2:
                    return None  # Accept if it's good or last chance or early in game
            
            # If offer is improving compared to the last one we rejected, be more flexible
            if len(self.opponent_history) > 1:
                prev_offer = self.opponent_history[-2]
                prev_value = sum(prev_offer[i] * self.values[i] for i in range(len(prev_offer)))
                
                if my_value_from_offer > prev_value:  # Getting better offers
                    # Be more willing to accept if we're seeing trend of improvement
                    if percentage_of_total >= current_threshold * 0.8:
                        return None
            
        # Make a counter-offer
        # Start with what we want, but be adaptive
        
        # Calculate what a fair share might be
        my_request = [0] * len(self.counts)
        
        # Based on our values, prioritize items we need most
        # But consider what the opponent might be looking for
        item_priorities = [(self.values[i], i) for i in range(len(self.values))]
        item_priorities.sort(key=lambda x: x[0], reverse=True)
        
        remaining_counts = self.counts[:]
        
        # First, ensure we get items that are valuable to us
        for _, idx in item_priorities:
            if remaining_counts[idx] > 0:
                if self.values[idx] > 0:  # Only take if we value the item
                    my_request[idx] = remaining_counts[idx]
                    remaining_counts[idx] = 0
                else:
                    my_request[idx] = 0
        
        # Check if our offer is reasonable - don't be greedy if that risks negotiation
        my_valuation = sum(my_request[i] * self.values[i] for i in range(len(my_request)))
        
        # If we're about to ask for everything (and leaving opponent with nothing)
        # adjust based on round and opponent behavior
        items_for_opponent = [self.counts[i] - my_request[i] for i in range(len(self.counts))]
        total_for_opponent = sum(items_for_opponent)
        
        # If we've asked for everything multiple times and gotten same offer back, compromise
        if total_for_opponent == 0 and self.rounds_elapsed > 1:
            # Give opponent at least something to break the deadlock
            for i in range(len(self.counts) - 1, -1, -1):  # Try least valuable items first
                if self.values[i] > 0 and my_request[i] > 0:
                    my_request[i] -= 1
                    break
        
        # Final checks to make sure our offer is valid and strategic
        for i in range(len(my_request)):
            my_request[i] = min(my_request[i], self.counts[i])
            my_request[i] = max(my_request[i], 0)
        
        # If we have historical data showing the opponent settles for less, we can be bolder
        if o is not None and self.rounds_elapsed < self.max_rounds:
            # If the current round offer is significantly better than our greedy one,
            # consider accepting instead of making another greedy counter-offer
            offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
            if offered_value >= 0.8 * self.total_value:
                return None  # Accept very good offers instead of being greedy
            
        return my_request