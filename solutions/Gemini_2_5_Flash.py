import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.negotiation_round = 0

        # Calculate a fair share value for ourselves
        self.fair_share = self.total_value_to_me / 2

        # Strategy parameters
        self.acceptance_threshold_min_ratio = 0.45  # Minimum value to accept, as a fraction of total_value_to_me
        self.initial_demand_max_ratio = 0.95 # Maximum initial demand, as a fraction of total_value_to_me
        self.concession_rate = 0.05 # How much we concede per round, per total possible rounds

    def _value_of_offer(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for self."""
        return sum(self.values[i] * offer_items[i] for i in range(len(offer_items)))

    def _generate_proportional_offer(self, target_value: float) -> list[int]:
        """
        Generates an offer that aims for a target value, prioritizing items
        with higher value-to-cost ratio (cost here is just 1 unit of the item).
        If the target value is not reached, it will try to fill the remaining
        slots with the most valuable items that are still available up to the target.
        """
        negotiation_offer = [0] * len(self.counts)
        current_value = 0
        
        # Create a list of items with their value, index, and remaining count for us to take
        item_data = []
        for i in range(len(self.counts)):
            if self.values[i] > 0: # Only consider items that have value to us
                item_data.append((self.values[i], i, self.counts[i]))
        
        # Sort items by value in descending order to prioritize higher-value items
        item_data.sort(key=lambda x: x[0], reverse=True)

        for value, item_idx, count in item_data:
            if current_value >= target_value:
                break

            # Add as many as possible of this item without exceeding its total count
            # or the desired target value
            num_to_add = min(count, math.ceil((target_value - current_value) / value))
            
            if num_to_add > 0:
                negotiation_offer[item_idx] += num_to_add
                current_value += num_to_add * value
        
        # If after prioritizing valuable items, we still haven't reached the target
        # (e.g., target might be higher than what we can get from valuable items),
        # or if we are slightly below due to integer division, try to add more.
        # This part ensures we get as close to the target value as possible
        # without exceeding the total available counts for any item type.
        if current_value < target_value:
            for value, item_idx, count in item_data:
                while negotiation_offer[item_idx] < self.counts[item_idx] and current_value + value <= target_value:
                    negotiation_offer[item_idx] += 1
                    current_value += value

        return negotiation_offer


    def offer(self, o: list[int] | None) -> list[int] | None:
        self.negotiation_round += 1
        # current_round is the total number of turns that have passed
        # e.g., if me=0, first turn: 0, second turn (partner): 1, third turn (me): 2
        # if me=1, first turn (partner): 0, second turn (me): 1
        current_turn = (self.negotiation_round - 1) * 2 + self.me 

        # Progress of negotiation from 0 to 1
        # The total number of offers possible is max_rounds * 2 (one from each player per round)
        # We use current_turn / (max_rounds * 2) for a smoother progression over all turns
        progress = current_turn / (self.max_rounds * 2) 

        # Determine current acceptance threshold:
        # It starts at acceptance_threshold_min_ratio * total_value_to_me
        # and slowly increases towards total_value_to_me as negotiations progress.
        # This means we become more desperate to accept more.
        # Using a quadratic function to make concessions faster towards the end.
        current_acceptance_value = self.total_value_to_me * \
                                   (self.acceptance_threshold_min_ratio + 
                                    (1 - self.acceptance_threshold_min_ratio) * (progress**2))
        
        # Determine current demand value:
        # It starts high (initial_demand_max_ratio * total_value_to_me)
        # and decreases over time, but never below our current acceptance threshold.
        initial_demand = self.total_value_to_me * self.initial_demand_max_ratio
        
        # Concession is based on total possible rounds, not just our turns
        concession = self.total_value_to_me * self.concession_rate * progress

        current_demand_value = max(current_acceptance_value, initial_demand - concession)
        
        if o is not None:
            value_of_partner_offer = self._value_of_offer(o)
            # If the partner's offer is at least as good as our current acceptance threshold, accept.
            if value_of_partner_offer >= current_acceptance_value:
                return None  # Accept the offer

        # Formulate a counter-offer
        # We try to get value equal to current_demand_value
        my_offer_items = self._generate_proportional_offer(current_demand_value)

        # Ensure the offer is valid by checking total counts
        for i in range(len(self.counts)):
            if my_offer_items[i] > self.counts[i]:
                my_offer_items[i] = self.counts[i] # Should ideally not happen with current _generate_proportional_offer, but as a safeguard.
            if my_offer_items[i] < 0:
                my_offer_items[i] = 0
            
        return my_offer_items