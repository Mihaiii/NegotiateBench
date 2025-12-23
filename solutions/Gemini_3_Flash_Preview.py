class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total_rounds = max_rounds
        self.current_round = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        # Rank items by value to us (highest first)
        self.pref_indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Increment round when it's our turn (either as 1st or 2nd mover)
        if self.me == 0 or o is not None:
            self.current_round += 1
        
        # Calculate turns remaining for the whole negotiation (2 turns per round)
        # Turn 1: Player 0, Turn 2: Player 1... Last Turn: Player 1 (Turn 2*max_rounds)
        total_turns = self.total_rounds * 2
        current_turn_count = (self.current_round - 1) * 2 + (1 if self.me == 0 else 2)
        turns_left = total_turns - current_turn_count

        # 1. Evaluate Partner's Offer
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Threshold
            # Be extremely firm early, but concede to ensure we don't get 0
            if turns_left <= 0:
                # Last possible turn (we are player 1): Accept anything > 0
                return None if offer_val > 0 or self.total_value == 0 else self._make_offer(0.5)
            
            progress = current_turn_count / total_turns
            if progress < 0.4:
                threshold = 0.9 * self.total_value
            elif progress < 0.7:
                threshold = 0.75 * self.total_value
            elif progress < 0.9:
                threshold = 0.6 * self.total_value
            else:
                threshold = 0.5 * self.total_value

            if offer_val >= max(threshold, 1):
                return None

        # 2. Construct Counter-Offer
        # Calculation of target ratio based on how much time is left
        if turns_left > total_turns * 0.5:
            target_ratio = 1.0
        elif turns_left > 2:
            # Gradually slide from 100% down to 60%
            rem_scale = (turns_left - 2) / (total_turns * 0.5)
            target_ratio = 0.6 + 0.4 * rem_scale
        else:
            # Final attempts: 50/50 split
            target_ratio = 0.5

        return self._make_offer(target_ratio)

    def _make_offer(self, ratio: float) -> list[int]:
        target_val = ratio * self.total_value
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Greedy selection of best items for us
        for i in self.pref_indices:
            if self.values[i] == 0: continue
            for _ in range(self.counts[i]):
                if current_val < target_val:
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    break

        # Strategic Concession: The Partner "Sweetener"
        # If we reached our target but didn't give the partner anything, they will reject.
        # Ensure they get something, starting with items worthless to us.
        partner_has_items = any((self.counts[i] - my_offer[i]) > 0 for i in range(len(self.counts)))
        
        if not partner_has_items:
            # Give them all items that are worth 0 to us
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = 0
            
            # If they still have nothing (no 0-value items exist), give 1 of our least valuable
            if sum(my_offer) == sum(self.counts):
                for i in reversed(self.pref_indices):
                    if my_offer[i] > 0:
                        my_offer[i] -= 1
                        break

        # Sanity check: Ensure we aren't returning an empty deal if we have value
        if sum(my_offer) == 0 and self.total_value > 0:
            my_offer[self.pref_indices[0]] = 1

        return my_offer