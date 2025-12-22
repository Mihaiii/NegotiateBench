import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.negotiation_round = 0
        
        # Strategy parameters - tuned for more dynamic behavior
        self.acceptance_threshold_start_ratio = 0.45  # Starting minimum value to accept
        self.acceptance_threshold_end_ratio = 0.9    # Ending minimum value to accept
        self.initial_demand_ratio = 0.95             # Initial demand as a fraction of total_value_to_me
        self.endgame_demand_ratio = 0.55             # Demand in the very last rounds

        # Pre-calculate item data for efficiency
        self.item_data = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                # Store (value_per_item, item_index, total_count_of_item)
                self.item_data.append((self.values[i], i, self.counts[i]))
        # Sort items by value in descending order, for greedy allocation
        self.item_data.sort(key=lambda x: x[0], reverse=True)


    def _value_of_offer(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for self."""
        return sum(self.values[i] * offer_items[i] for i in range(len(offer_items)))

    def _generate_proportional_offer(self, target_value: float) -> list[int]:
        """
        Generates an offer that aims for a target value, prioritizing items
        with higher value. It tries to get as close to the target value as possible
        without exceeding item counts.
        """
        negotiation_offer = [0] * len(self.counts)
        current_value = 0

        # Greedy approach: take highest value items first
        for value, item_idx, count in self.item_data:
            if current_value >= target_value:
                break
            
            # Determine how many of this item we can take
            # We can take up to 'count' of the item
            # We also try to take only what we need to reach the target_value
            remaining_value_needed = target_value - current_value
            num_to_take = min(count, math.floor(remaining_value_needed / value))
            
            negotiation_offer[item_idx] = num_to_take
            current_value += num_to_take * value

        # If we are still below target, try to fill up with remaining items, one by one,
        # to get closer without exceeding counts. This handles cases where
        # initial greedy might leave us slightly short.
        if current_value < target_value:
            for value, item_idx, count in self.item_data:
                while negotiation_offer[item_idx] < count and current_value + value <= target_value:
                    negotiation_offer[item_idx] += 1
                    current_value += value

        # Final check to ensure we don't accidentally offer more than available
        for i in range(len(self.counts)):
            if negotiation_offer[i] > self.counts[i]:
                negotiation_offer[i] = self.counts[i]

        return negotiation_offer


    def offer(self, o: list[int] | None) -> list[int] | None:
        self.negotiation_round += 1
        
        # Calculate negotiation progress (0.0 to 1.0)
        # Using (self.negotiation_round - 1) * 2 + self.me to get absolute turn number
        # to ensure progress is consistent regardless of who starts.
        absolute_turn = (self.negotiation_round - 1) * 2 + self.me
        # Divide by (max_rounds * 2 - 1) to make sure progress reaches 1.0 on the very last turn.
        progress = min(1.0, absolute_turn / (self.max_rounds * 2 - 1))

        # Dynamically adjust acceptance threshold and demand over time.
        # Acceptance threshold increases (we get more willing to accept less)
        current_acceptance_value = self.total_value_to_me * \
                                   (self.acceptance_threshold_start_ratio + 
                                    (self.acceptance_threshold_end_ratio - self.acceptance_threshold_start_ratio) * progress)

        # Demand decreases (we ask for less)
        current_demand_value = self.total_value_to_me * \
                               (self.initial_demand_ratio * (1 - progress) + \
                                self.endgame_demand_ratio * progress)
        
        # Make sure demand is at least as much as what we would accept.
        current_demand_value = max(current_demand_value, current_acceptance_value)

        # Consider partner's offer if available
        if o is not None:
            value_of_partner_offer = self._value_of_offer(o)
            
            # If the partner's offer is at or above our current acceptance threshold, accept.
            # Adding a small epsilon for floating point comparisons
            if value_of_partner_offer >= current_acceptance_value - 1e-6:
                return None  # Accept the offer

        # Formulate a counter-offer based on the calculated demand value
        my_offer_items = self._generate_proportional_offer(current_demand_value)

        # Ensure the sum of our offer and opponent's offer doesn't exceed total counts
        # This is crucial for a valid offer.
        # If this is the first turn and o is None, we assume the opponent gets 0 of everything for now
        # until they make their offer.
        if o is not None:
            # Calculate what the opponent wants based on their offer to us
            opponent_wants = [self.counts[i] - o[i] for i in range(len(self.counts))]
        else: # First turn for us, opponent hasn't made an offer yet
            opponent_wants = [0] * len(self.counts) 
            
        # Adjust offer if our current demand + what opponent wants from their last offer exceeds totals
        # This ensures our offer is "valid" in the sense that it doesn't claim more than available.
        # This is a bit of a heuristic. A more sophisticated approach would consider
        # common goods and find splits.
        adjusted_offer = my_offer_items[:]
        for i in range(len(self.counts)):
             # Ensure we don't ask for more than available considering opponent's last offer to us
            # This logic needs to consider "remaining" items after we take ours.
            # But since our offer is 'what I want', the other player should get 'total - what I want'.
            # We want to make sure 'total - what I want' for them is non-negative.
            # So, my_offer_items[i] <= self.counts[i] which is already handled in _generate_proportional_offer
            pass # The _generate_proportional_offer already limits to self.counts[i]

        return adjusted_offer