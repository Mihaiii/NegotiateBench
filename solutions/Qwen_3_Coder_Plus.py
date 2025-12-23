class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.max_offers = max_rounds * 2  # Total possible offers
        self.offer_number = 0  # Current position in the offer sequence
        self.total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        self.opponent_behavior = {}  # Track patterns in opponent's offers
        
        # Precompute some useful values
        self.item_values = values[:]
        self.total_items = sum(counts)

    def calculate_value(self, allocation):
        """Calculate value of an allocation according to my values."""
        return sum(allocation[i] * self.values[i] for i in range(len(allocation)))

    def find_acceptable_offer(self):
        """Find an offer to myself that's acceptable to me."""
        # Start with taking all high-value items for myself
        best_offer = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                best_offer.append(self.counts[i])
            else:
                best_offer.append(0)
        return best_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offer_number += 1
        current_round = (self.offer_number + 1) // 2  # Round number, starting at 1
        
        # If I received an offer, evaluate whether to accept it
        if o is not None:
            my_received_value = self.calculate_value(o)
            
            # Calculate how close this is to the end of negotiation
            offers_remaining = self.max_offers - self.offer_number
            deadline_pressure = offers_remaining / self.max_offers  # Value decreases as deadline approaches
            
            # Calculate my minimum acceptable value based on remaining time
            if self.offer_number > self.max_offers - 4:  # Last few offers
                threshold = self.total_value * 0.3  # Accept anything reasonable at the end
            elif self.offer_number > self.max_offers / 2:  # Past halfway point
                threshold = self.total_value * 0.6
            else:  # Early in the game
                threshold = self.total_value * 0.7
                
            # If it's good enough, accept it
            if my_received_value >= threshold:
                return None
        
        # Need to make a counter-offer

        # If starting the negotiation, make a reasonable first offer
        if o is None:
            # For first offer, take high-value items but leave some for the opponent
            my_offer = self.counts[:]
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    # If I don't value item i, I'll take only some of it
                    my_offer[i] = 0 if self.counts[i] < 2 else self.counts[i] // 2
                    
            # But make sure most high-value items go to me
            for i in range(len(self.counts)):
                if self.values[i] > 0 and self.counts[i] > 0:
                    # Keep majority of high-value items but leave some for incentive
                    needed = min(self.counts[i], self.counts[i] * 2 // 3 + 1 if self.counts[i] > 1 else self.counts[i]) 
                    my_offer[i] = needed
            return my_offer

        # For counter-offers, be strategic about improving my position
        # Based on the value I received and what I think is fair
        
        # Calculate what the opponent gets from current o
        opp_allocation = [self.counts[i] - o[i] for i in range(len(o))]
        
        # Make an offer that gives me better value while still offering the opponent 
        # something valuable to them (based on reverse inference)
        new_offer = [0] * len(self.counts)
        
        # Prioritize items I value highly
        valued_items = [(i, self.values[i]) for i in range(len(self.values))]
        valued_items.sort(key=lambda x: x[1], reverse=True)
        
        # For the remaining rounds, become more strategic about what I leave for opponent
        late_game = self.offer_number > self.max_offers * 0.7  # In last 30% of offers
        
        for idx, val in valued_items:
            if val > 0:  # Take items I value highly
                new_offer[idx] = self.counts[idx]
            else:  # For items I don't value, consider opponent's potential valuation
                # If we're in a late game situation, be more strategic about leaving something
                # valuable to opponent to incentivize acceptance
                if late_game:
                    # Leave more of valueless items to entice opponent
                    new_offer[idx] = self.counts[idx] // 2
                else:
                    # Early game - more aggressive on valueless items since 
                    # I can give opponent more of these later to sweeten the deal
                    new_offer[idx] = 0

        # If current offer to me is already quite good, don't be too aggressive
        my_received_value = self.calculate_value(o)
        if my_received_value >= self.total_value * 0.6:
            # Be more compromising
            for idx, val in valued_items:
                if val == 0:  # For zero value items, be more willing to compromise
                    if o[idx] < self.counts[idx]:
                        new_offer[idx] = max(new_offer[idx], o[idx])

        # Ensure we make an acceptable offer (don't offer more than available)
        for i in range(len(new_offer)):
            new_offer[i] = min(self.counts[i], new_offer[i])

        return new_offer