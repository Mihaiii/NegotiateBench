class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_elapsed = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Track opponent patterns and history
        self.opponent_history = []
        self.my_history = []
        self.acceptance_threshold = 0.4
        self.negotiation_state = "initial"

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_elapsed += 1
        
        # If opponent offered something
        if o is not None:
            # Record the offer
            self.opponent_history.append(o[:])
            
            # Calculate value of opponent's offer to me
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Check if we should accept based on value and game state
            offer_ratio = offer_value / self.total_value if self.total_value > 0 else 0
            
            # Adjust acceptance threshold based on time remaining
            time_factor = self.rounds_elapsed / self.max_rounds
            threshold = self.acceptance_threshold + (0.8 - self.acceptance_threshold) * time_factor
            
            # Detect if we're in a deadlock (same offer repeated)
            if len(self.opponent_history) >= 2 and self.opponent_history[-1] == self.opponent_history[-2]:
                # Be more flexible if getting same response
                threshold = max(0.3, threshold * 0.8)
            
            # If the offer is good enough relative to time and situation, accept
            if offer_ratio >= threshold:
                # Accept if good offer, or if low time remaining and we can't improve
                if time_factor > 0.8 or offer_ratio > 0.7:
                    return None
            
            # Check if opponent is being very generous
            if offer_ratio > 0.8:
                return None
        
        # Make a counter-offer if we're not accepting
        my_offer = self.create_counteroffer(o)
        
        # Track our counter-offer
        self.my_history.append(my_offer[:])
        
        return my_offer

    def create_counteroffer(self, opponent_offer):
        """Create a reasonable counter-offer based on our valuation and opponent's behavior"""
        
        # Start with asking for everything valuable to us
        desired = [0] * len(self.counts)
        for i in range(len(self.values)):
            if self.values[i] > 0:
                desired[i] = self.counts[i]
        
        # If there's an opponent offer, we need to adjust
        if opponent_offer:
            # Calculate what they value most highly and make some concession
            opponent_valuation = [0] * len(self.counts)
            
            # Estimate opponent's priority based on their offer
            # This is our best guess of what they value
            total_opp_value = sum(opponent_offer[i] * self.values[i] for i in range(len(opponent_offer)))
            
            # If we're at an impasse, make concessions
            if len(self.opponent_history) >= 2 and len(self.my_history) >= 2:
                # Check if recent offers are all the same (stuck in loop)
                all_my_offers_equal = len(set(tuple(offer) for offer in self.my_history[-3:])) == 1
                all_opp_offers_equal = len(set(tuple(offer) for offer in self.opponent_history[-3:])) == 1
                
                if all_my_offers_equal and all_opp_offers_equal:
                    # Break the cycle by making concessions
                    for i in range(len(self.counts)-1, -1, -1):  # Start from highest index
                        # Give opponent something valuable to us but important to them
                        if desired[i] > 0 and self.counts[i] > 1:
                            desired[i] = max(0, desired[i] - 1)
                            break

        # Make sure our offer doesn't exceed available items
        for i in range(len(desired)):
            desired[i] = min(desired[i], self.counts[i])
        
        # Check if we have all high-value items, consider sharing lower-value ones to break deadlock
        my_valuation = sum(desired[i] * self.values[i] for i in range(len(desired)))
        
        # If we're asking for too much and the opponent might feel we're unreasonable
        items_i_keep = sum(desired[i] for i in range(len(desired)))
        items_opponent_gets = sum(self.counts[i] - desired[i] for i in range(len(desired)))
        
        # If I'm getting everything, I must share something unless I already have a very good deal
        if items_opponent_gets == 0 and self.rounds_elapsed > 1:
            # Give them at least one item of value to them (we'll estimate)
            # In this case, give up something with lowest value to us
            if self.values.count(0) == 0:  # All items have value
                min_val_idx = min(range(len(self.values)), key=lambda k: self.values[k])
                if self.values[min_val_idx] == min(self.values) and desired[min_val_idx] > 0:
                    desired[min_val_idx] = max(0, desired[min_val_idx] - 1)
            else:
                # Give up an item worth 0 to us if any
                for i in range(len(self.values)):
                    if self.values[i] == 0 and desired[i] > 0:
                        desired[i] = 0
                        break
                # If no 0-value items, give up a low-value one
                else:
                    min_val_idx = min(range(len(self.values)), key=lambda k: self.values[k])
                    if desired[min_val_idx] > 0:
                        desired[min_val_idx] = max(0, desired[min_val_idx] - 1)
                        
        return desired