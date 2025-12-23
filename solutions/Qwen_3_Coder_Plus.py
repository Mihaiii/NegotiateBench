import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Track negotiation history
        self.offer_count = 0
        self.offers_received = []
        self.offers_made = []
        self.opponent_pattern = {}  # Track opponent's preferences based on their offers

    def calculate_value(self, allocation):
        """Calculate the value of an allocation based on my values"""
        return sum(a * v for a, v in zip(allocation, self.values))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offer_count += 1
        
        turn_num = self.offer_count
        remaining_turns = self.max_rounds * 2 - turn_num
        current_round = (turn_num + 1) // 2  # Round number (1-indexed)
        
        # If received an offer, decide whether to accept it
        if o is not None:
            received_value = self.calculate_value(o)
            self.offers_received.append((o, received_value))
            
            # Analyze opponent's previous offers to detect pattern
            self._update_opponent_pattern(o)
            
            # Dynamic acceptance threshold based on remaining turns and negotiation progress
            threshold = self._calculate_acceptance_threshold(remaining_turns, received_value)
            
            if received_value >= threshold:
                # Accept if the offer is good enough
                return None

        # Make a counter-offer
        if o is None:
            my_offer = self._make_initial_offer(current_round)
        else:
            my_offer = self._make_counter_offer(o, remaining_turns, current_round)

        # Validate offer is within bounds
        for i in range(len(my_offer)):
            my_offer[i] = min(my_offer[i], self.counts[i])
        
        self.offers_made.append(my_offer)
        return my_offer

    def _calculate_acceptance_threshold(self, remaining_turns, current_offer_value):
        """Calculate dynamic acceptance threshold based on remaining time and negotiation progress"""
        if remaining_turns <= 2:  # Near the end
            # Be more flexible near deadline
            return max(self.total_value * 0.3, current_offer_value * 0.9)
        elif remaining_turns <= 6:
            # Moderate acceptance: value of offer vs what we expect to get
            base_threshold = self.total_value * 0.5
            if self.offers_received:
                avg_received = sum(v for _, v in self.offers_received[-3:]) / min(len(self.offers_received), 3)
                base_threshold = max(base_threshold, avg_received * 0.8)
            return base_threshold
        else:
            # Early on: be more demanding
            base_threshold = self.total_value * 0.7
            if self.offers_received:
                recent_high = max(v for _, v in self.offers_received[-3:]) if self.offers_received else 0
                return max(base_threshold, recent_high * 0.7)
            return base_threshold

    def _update_opponent_pattern(self, opponent_offer):
        """Track what items opponent consistently values highly"""
        if not self.offers_received:
            for i in range(len(opponent_offer)):
                self.opponent_pattern[i] = opponent_offer[i]
        else:
            # Refine pattern based on multiple offers
            for i, count in enumerate(opponent_offer):
                current_pattern_value = self.opponent_pattern.get(i, 0)
                # Weight newer offers more heavily
                self.opponent_pattern[i] = max(current_pattern_value, count)

    def _make_initial_offer(self, current_round):
        """Make initial offer based on my priorities"""
        offer = [0] * len(self.counts)
        
        # Prioritize items I value most
        items_by_value = [(i, self.values[i], self.counts[i]) for i in range(len(self.counts))]
        items_by_value.sort(key=lambda x: x[1], reverse=True)  # Sort by value, highest first
        
        for idx, val, count in items_by_value:
            if val > 0:
                # Take all if it has high value and quantity is small
                if count == 1:
                    offer[idx] = count
                else:
                    # Take majority but leave some if there are multiple
                    offer[idx] = max(count - 1, count // 2 + 1)  # Keep more than half but not all
            else:
                offer[idx] = 0  # Skip worthless items for me
                
        return offer

    def _make_counter_offer(self, prev_opponent_offer, remaining_turns, current_round):
        """Make a strategic counter-offer"""
        counter = [0] * len(self.counts)
        
        # Determine opponent's allocation from their offer to me
        opp_allocation = [self.counts[i] - prev_opponent_offer[i] for i in range(len(self.counts))]
        
        # Create counter-offer based on my preferences but responsive to opponent
        sorted_items = []
        for i in range(len(self.counts)):
            my_val = self.values[i]
            opp_preference = self.counts[i] - opp_allocation[i]  # What opponent got
            sorted_items.append((i, my_val, self.counts[i], opp_preference))
        
        # Sort primarily by my value, secondarily to consider opponent's interest
        sorted_items.sort(key=lambda x: (x[1], -x[3]), reverse=True)
        
        my_total_value = 0
        
        for idx, my_val, count, opp_requested in sorted_items:
            if my_val > 0:
                if count == 1:
                    # Only one item - take it if it's valuable
                    counter[idx] = 1
                else:
                    # Multiple items: try to balance keeping valuable but not being too greedy
                    if remaining_turns <= 4:  # Near deadline, be more flexible
                        needed_for_good_deal = max(1, count // 2)
                        if my_val >= self.total_value * 0.1:  # High value item, keep most
                            counter[idx] = max(needed_for_good_deal, count - opp_requested)
                        else:
                            # Lower value but still worth taking some
                            counter[idx] = max(0, count - (opp_requested + 1) // 2)
                    else:
                        # Early/middle game: take majority
                        counter[idx] = max(count // 2 + 1, 1)
            else:
                # No value to me: consider leaving more of these for opponent
                # But also consider if the opponent is being uncooperative overall
                if remaining_turns <= 6:
                    # Deadline approaching - make offer more palatable
                    counter[idx] = max(0, count // 2)  # Offer compromise
                else:
                    counter[idx] = 0  # Give to opponent if worthless to me
                            
            counter[idx] = min(counter[idx], count)  # Don't exceed count
            counter[idx] = max(0, counter[idx])      # Don't give negative
            
            my_total_value += counter[idx] * my_val
        
        # Ensure we don't exceed available counts
        for i in range(len(counter)):
            counter[i] = min(max(0, counter[i]), self.counts[i])
            
        return counter