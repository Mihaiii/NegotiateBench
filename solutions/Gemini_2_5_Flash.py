class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        self.current_round = 0
        if me == 1:  # If starting second, effectively round 0 has passed from my perspective
            self.current_round = 0.5 
        
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)
        
        self.initial_demand_ratio = 1.0  # Start by demanding everything
        self.my_last_offer = None # To remember what I offered last

    def calculate_value(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for me."""
        return sum(self.values[i] * offer_items[i] for i in range(self.num_object_types))

    def create_my_offer(self, target_value_ratio: float) -> list[int]:
        """
        Creates an offer for myself aiming for a certain percentage (ratio) of the total value.
        It prioritizes getting more valuable items first while respecting counts.
        """
        
        if self.total_value_to_me == 0:
            return [0] * self.num_object_types

        target_value_ratio = max(0.0, min(1.0, target_value_ratio))
        target_value = int(self.total_value_to_me * target_value_ratio)
        my_offer_counts = [0] * self.num_object_types
        current_value = 0
        
        # Sort items by value_per_item in descending order.
        item_info = []
        for i in range(self.num_object_types):
            item_info.append((self.values[i], i))
        item_info.sort(key=lambda x: x[0], reverse=True)

        # Iterate through items, trying to add them to the offer to reach the target_value
        for value_per_item, item_idx in item_info:
            if current_value >= target_value:
                break

            if value_per_item > 0: # Only consider valuable items for reaching the target value
                num_can_take = self.counts[item_idx]
                
                # Calculate how many of the current item type we need to reach the target_value
                needed_for_target = (target_value - current_value + value_per_item - 1) // value_per_item # Ceiling division
                
                num_to_take = min(num_can_take, needed_for_target)
                
                my_offer_counts[item_idx] += num_to_take
                current_value += num_to_take * value_per_item
            
        # After fulfilling target value with valuable items, distribute remaining zero-value items.
        # If an item type is completely worthless to me, I'm indifferent to getting it or not.
        # To make my offer more appealing, I can offer all worthless items to the partner if I don't need them.
        # However, to be more robust, I'll take them myself if they are worthless to me, unless partner explicitly offers them.
        for i in range(self.num_object_types):
            if self.values[i] == 0:
                my_offer_counts[i] = self.counts[i] # Take all worthless items

        return my_offer_counts

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is None:  # First offer by me
            self.current_round = 0
        else: # Offer received, it's my turn to respond
            self.current_round += 0.5 # Each person gets a turn in a round, so 0.5 per offer

        total_turns = self.max_rounds * 2 
        
        # Calculate negotiation progress (0.0 to 1.0)
        # Using self.current_round / self.max_rounds for progress to represent round progression more directly.
        progress = self.current_round / self.max_rounds
        progress = min(progress, 1.0) # Cap progress at 1.0

        # Dynamic demand ratio: start high, decrease over time.
        # Aim for at least 50% of my total value.
        
        min_acceptable_ratio = 0.5
        if self.total_value_to_me == 0:
            min_acceptable_ratio = 0.0 # If I value nothing, I'll accept 0.

        # A more aggressive decay that starts higher and drops faster.
        # Using a cubic decay towards the end.
        demand_ratio_decay = (1 - progress) ** 3
        
        # The range of demand will be between initial_demand_ratio (1.0) and min_acceptable_ratio.
        demand_ratio = min_acceptable_ratio + (self.initial_demand_ratio - min_acceptable_ratio) * demand_ratio_decay

        # Ensure demand ratio doesn't exceed 1.0 or fall below 0.0
        demand_ratio = max(min(demand_ratio, 1.0), 0.0)

        # Check if it's the absolute last turn for *me* to accept an offer.
        # This implies it's my turn in the very last round.
        is_my_last_turn_to_act = (self.current_round == self.max_rounds - 0.5 and self.me == 0) or \
                                 (self.current_round == self.max_rounds and self.me == 1)
        is_last_offer_possible = self.current_round < self.max_rounds


        # If an offer was made to me:
        if o is not None:
            offer_value = self.calculate_value(o)
            
            # Acceptance conditions:
            # 1. The offer meets or exceeds my current calculated demand ratio.
            # 2. It's the absolute last turn for me to act, and the offer provides *any* positive value to me, preventing a total loss.
            # 3. If everything is worthless to me, and the partner offers me 0, I accept.
            
            # If the offer is good enough based on current demand ratio
            if offer_value >= self.total_value_to_me * demand_ratio:
                return None  # Accept offer
            
            # If it's the very last moment to accept to avoid getting nothing
            if not is_last_offer_possible:
                if offer_value > 0 or self.total_value_to_me == 0 : # Accept if it gives me something, or if I value nothing anyway
                    return None
            
            # If I value nothing at all, and the offer gives me nothing (which is all I care about)
            if self.total_value_to_me == 0 and offer_value == 0:
                return None

        # Create counter-offer (or initial offer)
        my_offer_to_make = self.create_my_offer(demand_ratio)
        
        # If it's the very last round and I still need to make an offer, be more flexible
        # to ensure a deal if possible, even if it means accepting a lower value.
        if not is_last_offer_possible: 
            # Make a more generous offer to try and secure SOMETHING if faced with no deal.
            # Here, I'm setting my demand to just break even (0.5) or slightly above if I'm first.
            final_concession_ratio = min_acceptable_ratio 
            
            # If I am the one making the last offer, I'd aim for slightly above 0.5 to make it seem like a good deal.
            # But in the spirit of avoiding no deal, I concede to 0.5.
            if self.total_value_to_me == 0:
                final_concession_ratio = 0.0

            my_offer_to_make = self.create_my_offer(final_concession_ratio)

        self.my_last_offer = my_offer_to_make 
        return my_offer_to_make