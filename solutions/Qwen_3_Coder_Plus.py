import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Keep track of offers and counter-offers
        self.offers_received = []
        self.offer_count = 0
        self.opponent_last_offer = None

    def calculate_value(self, allocation):
        """Helper to calculate the value of an allocation based on my values"""
        return sum(a * v for a, v in zip(allocation, self.values))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offer_count += 1
        
        # If received an offer, decide whether to accept it
        if o is not None:
            received_value = self.calculate_value(o)
            
            # Update opponent's last offer
            self.opponent_last_offer = o
            self.offers_received.append(received_value)
            
            # Remaining rounds (both parties get a turn, so it's rounds * 2 - current number of offers)
            remaining_offers = self.max_rounds * 2 - self.offer_count
            
            # Threshold value decreases as negotiation approaches deadline
            # Early on: be demanding; late: be more accepting
            if remaining_offers <= 2:  # Near the end - accept reasonably good offers
                threshold = self.total_value * 0.5
            elif remaining_offers <= 4:
                threshold = self.total_value * 0.6
            elif remaining_offers <= 8:
                threshold = self.total_value * 0.7
            else:
                threshold = self.total_value * 0.8  # Be demanding at the start
            
            if received_value >= threshold:
                return None  # Accept the offer

        # Make a counter-offer
        if o is None:
            # First offer - be strategic
            my_offer = self._make_initial_offer()
        else:
            # Counter-offer based on previous offers
            my_offer = self._make_counter_offer(o)

        # Return my offer
        return my_offer

    def _make_initial_offer(self):
        """Make an initial offer with a fair distribution but tilted in my favor"""
        # Start with taking all high-value items
        offer = [0] * len(self.counts)
        
        # For each item type, decide allocation based on value importance
        # Allocate most valuable items to me, but be strategic
        items_by_value = [(i, self.values[i], self.counts[i]) for i in range(len(self.counts))]
        items_by_value.sort(key=lambda x: x[1], reverse=True)  # Sort by value, highest first
        
        for idx, val, count in items_by_value:
            if val > 0:
                # For high-value items, keep majority but potentially leave some
                if count == 1:
                    offer[idx] = count  # Take it if there's only one
                else:
                    offer[idx] = max(math.ceil(count * 0.6), 1)  # Keep 60% or at least 1
            else:
                offer[idx] = 0  # Don't need items with 0 value
        
        # Make sure we don't offer more than what's available
        for idx in range(len(offer)):
            offer[idx] = min(offer[idx], self.counts[idx])
            
        return offer

    def _make_counter_offer(self, prev_opponent_offer):
        """Make a counter-offer based on my preferences and the opponent's offer"""
        # Start with my initial strategy
        counter = [0] * len(self.counts)
        
        # Calculate the opponent's remaining allocation from the prev_opponent's offer to me
        opp_allocation = [self.counts[i] - prev_opponent_offer[i] for i in range(len(self.counts))]
        
        # For each item type, consider what the opponent prioritizes vs. what I want
        # Use this to find a compromise that satisfies me but gives opponent something they might want
        
        # Sort items by my value
        items_by_my_value = [(i, self.values[i], self.counts[i]) for i in range(len(self.counts))]
        items_by_my_value.sort(key=lambda x: x[1], reverse=True)
        
        # Calculate value from the previous offer
        prev_offer_value = self.calculate_value(prev_opponent_offer)
        
        # Base counter-offer on what I want, being flexible with items I value less
        for idx, my_val, count in items_by_my_value:
            if my_val > 0:
                # Take as much as possible of high-value items
                counter[idx] = count
            else:
                # For zero-value items, consider opponent's perspective
                # If opponent wants it a lot in their offer to me, maybe they value it highly
                opp_gets_from_prev = self.counts[idx] - prev_opponent_offer[idx]  # What opponent gets in their proposed split
                counter[idx] = 0  # Let opponent keep items I don't value
                
        # Ensure we don't exceed counts
        for i in range(len(counter)):
            counter[i] = min(counter[i], self.counts[i])
            
        # Adjust based on stage in the game and if opponent seems willing to compromise
        remaining_offers = self.max_rounds * 2 - self.offer_count
        
        if remaining_offers <= 4:
            # Near the end, be more willing to compromise toward a deal
            # Try to find an offer that might be acceptable to both parties
            best_offer = counter[:]
            
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    # Consider leaving some of valueless items to make offer more palatable
                    if opp_allocation[i] > 0 and count > 1:
                        best_offer[i] = max(0, count // 2)  # Offer compromise
            
            # Make sure the offer is still acceptable to me
            if self.calculate_value(best_offer) >= ((prev_offer_value + self.total_value) / 2) * 0.5 \
               or self.calculate_value(best_offer) >= self.total_value * 0.6:
                counter = best_offer
        
        return counter