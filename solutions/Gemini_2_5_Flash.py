class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        # current_turn will track the total number of turns elapsed (0-indexed)
        # If I go first (me=0), my turns are 0, 2, 4, ...
        # If I go second (me=1), my turns are 1, 3, 5, ...
        self.current_turn = 0 if me == 0 else 1
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)

    def calculate_value(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for me."""
        return sum(self.values[i] * offer_items[i] for i in range(self.num_object_types))

    def create_my_offer(self, min_value_percentage: float) -> list[int]:
        """
        Creates an offer for myself aiming for a certain percentage of the total value.
        It prioritizes getting more valuable items first.
        """
        target_value = int(self.total_value_to_me * min_value_percentage)
        my_offer = [0] * self.num_object_types
        current_value = 0

        # Create a list of tuples (value_per_item, item_index) and sort by value_per_item (descending)
        # For items of same value, sort by count (descending) to prefer taking more of common valuable items
        item_priorities = sorted(
            [(self.values[i], self.counts[i], i) for i in range(self.num_object_types)],
            key=lambda x: (x[0], x[1]),  # Sort by value then by count
            reverse=True
        )

        # First pass: try to reach the target value by picking full items
        for value_per_item, total_count, item_idx in item_priorities:
            if value_per_item == 0:
                continue # Skip worthless items for now

            for _ in range(total_count):
                if current_value + value_per_item <= target_value:
                    my_offer[item_idx] += 1
                    current_value += value_per_item
                else:
                    # If adding this item exceeds target, and we already have some,
                    # consider if it takes us too far over. Otherwise, move to next item type.
                    # For simplicity here, we stop adding this item type if it exceeds.
                    break
        
        # Second pass: if target not met, add items even if it slightly exceeds,
        # preferring more valuable items. Also ensures all items are distributed.
        # This also handles the case where target_value is low and initial pass didn't pick anything.
        for value_per_item, total_count, item_idx in item_priorities:
            remaining_to_take = self.counts[item_idx] - my_offer[item_idx]
            for _ in range(remaining_to_take):
                if current_value < target_value: # Still under target, take it
                    my_offer[item_idx] += 1
                    current_value += value_per_item
                elif value_per_item > 0 and current_value == 0: # If we have nothing, take at least one valuable item.
                    my_offer[item_idx] += 1
                    current_value += value_per_item
                elif value_per_item > 0 and current_value < self.total_value_to_me * (min_value_percentage + 0.1): # Allow slight overshoot to get valuable items
                    my_offer[item_idx] += 1
                    current_value += value_per_item
                elif value_per_item == 0: # Take all worthless items if not yet at total_count
                    my_offer[item_idx] += 1
                    current_value += value_per_item

        # Ensure that no item is offered more than available
        for i in range(self.num_object_types):
            my_offer[i] = min(my_offer[i], self.counts[i])
            
        # Ensure all items are accounted for, if not, assign remaining to partner
        # (This is handled implicitly by the negotiation framework, but good for internal consistency)
        
        return my_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            # If I'm turn 0, partner just made offer, so current_turn advances
            # If I'm turn 1, partner just made offer, which starts my turn, so current_turn advances
            self.current_turn += 1
        
        # Total number of turns in the negotiation (e.g., 2 * max_rounds)
        total_possible_turns = self.max_rounds * 2 
        
        # Calculate a dynamic minimum value percentage I am willing to accept or demand.
        # This percentage will decrease as negotiations progress.
        # We want to start high and end up lower to ensure a deal.
        initial_min_val_percentage = 0.95  # Start demanding a high percentage
        final_min_val_percentage = 0.45   # Be willing to accept less at the end

        # Linear reduction from initial to final percentage over the course of negotiations
        if total_possible_turns > 1:
            # The 'turns_remaining' dictates how aggressive we can be.
            # current_turn is 0-indexed.
            turns_progress = self.current_turn / (total_possible_turns - 1)
            my_required_percentage = initial_min_val_percentage - (
                turns_progress * (initial_min_val_percentage - final_min_val_percentage)
            )
        else:
            my_required_percentage = initial_min_val_percentage
        
        # Ensure percentage doesn't go below the final threshold
        my_required_percentage = max(my_required_percentage, final_min_val_percentage)

        # If it's the very last possible turn for me to make an offer, be very flexible
        # if the current offer is not None.
        is_my_last_chance_to_make_offer = (self.current_turn == total_possible_turns - 1)

        if o is not None:
            # Evaluate partner's offer
            offer_value = self.calculate_value(o)
            
            # Condition to accept:
            # 1. Offer meets or exceeds my current required percentage.
            # 2. It's the very last negotiation turn and the offer is positive.
            #    This is crucial to avoid "no deal" if my partner also lowers their demand
            #    significantly on the last turn.
            if offer_value >= self.total_value_to_me * my_required_percentage or \
               (is_my_last_chance_to_make_offer and offer_value > 0):
                return None  # Accept offer

        # If it's my turn to make an offer (either first turn, or I rejected partner's offer)
        # If it's the last turn and I haven't accepted, I MUST make a reasonable offer
        # to try and ensure a deal.
        if is_my_last_chance_to_make_offer and o is None: # Only relevant if I initiated the last turn
             # On the absolute last turn, I will propose an offer that is 50/50 or slightly better if possible
             # by making sure my required percentage is at least 0.5.
            my_required_percentage = max(my_required_percentage, 0.5 )
            return self.create_my_offer(my_required_percentage)
        elif is_my_last_chance_to_make_offer and o is not None: # Partner offered, I rejected, now it's my counter
             # On the absolute last turn, I will propose an offer that is 50/50 or slightly better if possible
            my_required_percentage = max(my_required_percentage, 0.5)
            # Make sure I don't demand more than what is available after partner's offer (which has been rejected)
            # This logic is about the overall deal, not relative to partner's last offer.
            return self.create_my_offer(my_required_percentage)
        
        return self.create_my_offer(my_required_percentage)