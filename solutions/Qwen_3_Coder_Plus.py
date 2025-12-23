import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Track negotiation history
        self.turn_count = 0
        self.offers_received = []
        self.offers_made = []
        self.opponent_values_estimate = [0] * len(counts)  # Estimate of opponent's values

    def calculate_value(self, allocation):
        """Calculate the value of an allocation based on my values"""
        return sum(a * v for a, v in zip(allocation, self.values))

    def _estimate_opponent_values(self, offers):
        """Estimate opponent's values based on their offers and rejections"""
        if not offers:
            return [0] * len(self.counts)
        
        # The items they don't offer/keep frequently might be more valuable to them
        # Use frequency and how much they fight for items to estimate values
        estimation = [0] * len(self.counts)
        
        for offer in offers:
            # Higher estimation for items they keep to themselves (don't offer to me)
            for i in range(len(offer)):
                # What they're keeping: counts[i] - offer[i]
                items_they_keep = self.counts[i] - offer[i]
                # If they keep more of an item, it might be more valuable to them
                if items_they_keep > 0:
                    estimation[i] = max(estimation[i], items_they_keep)
        
        return estimation

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        remaining_turns = self.max_rounds * 2 - self.turn_count + 1
        current_round = (self.turn_count + 1) // 2

        if o is not None:
            received_value = self.calculate_value(o)
            self.offers_received.append(o)
            
            # Update opponent value estimation
            self.opponent_values_estimate = self._estimate_opponent_values(self.offers_received)
            
            # Calculate expected value for opponent of this offer
            opponent_gets = [self.counts[i] - o[i] for i in range(len(self.counts))]
            
            # Dynamic threshold based on position in game and opponent's pattern
            if remaining_turns <= 2:  # Near the end, be more flexible
                threshold = self.total_value * 0.3  # Lower threshold near end
            elif remaining_turns <= 6:
                threshold = self.total_value * 0.5  # Medium threshold
            else:
                threshold = self.total_value * 0.65  # Higher requirement early
        
            # If this offer meets our threshold, accept it
            if received_value >= threshold:
                return None

            # Also consider if this offer is actually the best we can reasonably expect
            expected_deal_value = self._estimate_max_possible_value()
            if received_value >= 0.8 * expected_deal_value:
                return None

        # Make a counter-offer
        my_offer = self._strategic_counter_offer(o, remaining_turns)
        self.offers_made.append(my_offer)
        return my_offer

    def _estimate_max_possible_value(self):
        """Estimate maximum possible value considering opponent's likely preferences"""
        # Look at what has been observed about their behavior so far
        if not self.offers_received:
            return self.total_value
        
        max_possible_valuations = [0] * len(self.counts)
        for i in range(len(self.counts)):
            if self.opponent_values_estimate[i] == 0:
                # If they seem to care more about it, let them have some
                max_possible_valuations[i] = self.values[i] * self.counts[i] 
            else:
                # If they value it highly, I might not get much of it
                # The more their relative value vs mine, the less I expect to get
                if self.values[i] > 0:  # Only if I value it too
                    max_possible_valuations[i] = self.values[i] * self.counts[i] * 0.7  # Discount for competition
                else:
                    max_possible_valuations[i] = 0
        
        return sum(max_possible_valuations)

    def _strategic_counter_offer(self, prev_opponent_offer, remaining_turns):
        """Make a strategic counter-offer based on analysis of opponent's preferences"""
        my_offer = [0] * len(self.counts)
        
        # Prioritize items by value ratio between my valuation and estimated opponent's
        items_importance = []
        
        for i in range(len(self.counts)):
            my_val = self.values[i]
            opp_est_val = self.opponent_values_estimate[i]
            
            if self.counts[i] == 0:
                my_offer[i] = 0
                continue
            
            # Calculate importance: if opponent values it less, I should try to get more of it
            if opp_est_val == 0:
                importance = my_val  # They don't want it, prioritize it for me
            elif my_val == 0 and opp_est_val > 0:
                importance = -opp_est_val  # I don't want it, they do, consider giving more to them
            else:
                # Both want it, prioritize by how much more I value it compared to them
                importance = my_val - opp_est_val if opp_est_val > 0 else my_val
            
            items_importance.append((i, my_val, opp_est_val, importance, self.counts[i]))

        # Sort by importance (descending)
        items_importance.sort(key=lambda x: x[3], reverse=True)

        # Allocate items based on importance and availability
        remaining_items = self.counts[:]
        
        for idx, my_val, opp_val, importance, total_count in items_importance:
            if remaining_items[idx] <= 0:
                continue
                
            if importance > 0:  # I value this more than opponent (or only me values it)
                # Take more of high-priority items
                if remaining_turns <= 4:  # Near end, be less greedy
                    my_offer[idx] = min(remaining_items[idx], max(remaining_items[idx] // 2, 1))
                else:
                    # Take more if it's highly valuable to me and not opponent
                    if my_val > 0 and my_val >= max(2, opp_val * 1.5):
                        my_offer[idx] = remaining_items[idx]  # Take all if I value much more
                    else:
                        # Take most but not all to be somewhat compromising, if not the last few rounds
                        my_offer[idx] = max(1, remaining_items[idx] // 2 + (remaining_items[idx]+1) // 2)
                
            elif importance < 0:  # Opponent values it more than me (or only they value it)
                # Consider leaving more for opponent to reach agreement
                if remaining_turns <= 6:  # End game: be more compromising
                    my_offer[idx] = min(remaining_items[idx] // 4 + 1, remaining_items[idx])
                else:
                    # Early on: take some high-value items for myself, give them the rest
                    my_offer[idx] = 0  # Give all to opponent if they value it much more
            else:  # Equal value
                # Split more evenly, especially as we get closer to the deadline
                if remaining_turns <= 6:
                    my_offer[idx] = remaining_items[idx] // 2
                else:
                    my_offer[idx] = remaining_items[idx] // 2 + 1 if remaining_items[idx] % 2 == 1 else remaining_items[idx] // 2

            # Make sure to stay within bounds
            my_offer[idx] = min(my_offer[idx], remaining_items[idx])
            my_offer[idx] = max(0, my_offer[idx])

        # Ensure we don't have any negative values due to calculation errors
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(my_offer[i], self.counts[i]))

        return my_offer