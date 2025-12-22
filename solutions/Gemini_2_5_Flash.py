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
        self.acceptance_threshold_min = 0.45  # Minimum value to accept, as a fraction of total_value_to_me
        self.acceptance_threshold_max = 0.85 # Maximum initial demand, as a fraction of total_value_to_me
        self.concession_rate = 0.03 # How much we concede per round

    def _value_of_offer(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for self."""
        return sum(self.values[i] * offer_items[i] for i in range(len(offer_items)))

    def _generate_proportional_offer(self, target_value: float) -> list[int]:
        """
        Generates an offer that aims for a target value, prioritizing items
        with higher value-to-cost ratio (cost here is just 1 unit of the item).
        """
        negotiation_offer = [0] * len(self.counts)
        current_value = 0
        remaining_counts = list(self.counts)

        # Create a list of items with their value and index
        # Prioritize items that are valuable to me
        item_scores = sorted(
            [
                (self.values[i], i)
                for i in range(len(self.counts))
            ],
            key=lambda x: x[0],
            reverse=True
        )

        for value, item_idx in item_scores:
            if current_value >= target_value:
                break

            available_for_me = min(remaining_counts[item_idx], self.counts[item_idx])
            
            # Add as many as possible without exceeding remaining_counts or desired value
            for _ in range(available_for_me):
                if current_value + value <= target_value:
                    negotiation_offer[item_idx] += 1
                    current_value += value
                    remaining_counts[item_idx] -= 1
                else:
                    break
        
        # If we still haven't reached the target,
        # iterate through all items again, adding what we can
        # to get closer to the target without going over remaining_counts.
        if current_value < target_value:
            for item_idx in range(len(self.counts)):
                value = self.values[item_idx]
                while negotiation_offer[item_idx] < self.counts[item_idx] and current_value + value <= target_value:
                    negotiation_offer[item_idx] += 1
                    current_value += value
        
        return negotiation_offer


    def offer(self, o: list[int] | None) -> list[int] | None:
        self.negotiation_round += 1
        current_round = (self.negotiation_round - 1) * 2 + (self.me) # 0-indexed across all turns

        # Dynamically adjust acceptance and offer thresholds
        # Towards the end, be more willing to accept less.
        # Early on, demand more.
        progress = current_round / (self.max_rounds * 2)
        
        # Acceptance threshold increases (we accept less) as negotiations progress
        current_acceptance_threshold = self.total_value_to_me * (self.acceptance_threshold_min + (1 - self.acceptance_threshold_min) * progress**2)
        
        # Offer value decreases as negotiations progress
        initial_demand_value = self.total_value_to_me * self.acceptance_threshold_max
        current_demand_value = max(current_acceptance_threshold, initial_demand_value - self.total_value_to_me * self.concession_rate * current_round)


        if o is not None:
            value_of_partner_offer = self._value_of_offer(o)
            if value_of_partner_offer >= current_acceptance_threshold:
                return None  # Accept the offer

        # Formulate a counter-offer
        # Start demanding high and concede over time
        
        my_offer_items = self._generate_proportional_offer(current_demand_value)
        return my_offer_items