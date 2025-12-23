class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if first, 1 if second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.turn_count = 0
        
        # Calculate total value for us
        self.total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        
        # Track what the opponent has offered in previous turns
        self.opponent_offers = []
        
        # Track our own offers
        self.my_offers = []
        
        # Prioritize items by our value (highest first)
        self.item_priority = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)
    
    def calculate_value(self, offer: list[int]) -> int:
        """Calculate the value of an offer to us."""
        return sum(offer[i] * self.values[i] for i in range(len(offer)))
    
    def calculate_opponent_share(self, offer: list[int]) -> list[int]:
        """Calculate what we get from opponent's offer (they keep what they offer for themselves)."""
        return [self.counts[i] - offer[i] for i in range(len(self.counts))]
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # If this is the first turn and we're first, make an initial offer
        if o is None:
            offer = self.make_initial_offer()
            self.my_offers.append(offer)
            return offer
        
        # Record the opponent's offer
        self.opponent_offers.append(o)
        
        # Calculate the value of the opponent's offer to us
        our_share = self.calculate_opponent_share(o)
        offer_value = self.calculate_value(our_share)
        
        # Determine if we should accept the offer
        if self.should_accept(offer_value):
            return None
        
        # Otherwise, make a counter-offer
        offer = self.make_counter_offer(o, offer_value)
        self.my_offers.append(offer)
        return offer
    
    def make_initial_offer(self) -> list[int]:
        """Make an initial offer asking for a fair share plus a bit more."""
        offer = [0] * len(self.counts)
        
        # Ask for items with the highest value first
        current_value = 0
        target_value = self.total_value * 0.65  # Aim for 65% initially
        
        for i in self.item_priority:
            if current_value >= target_value:
                break
            # Ask for as many of this item as needed to reach the target
            if self.values[i] > 0:
                needed = (target_value - current_value) / self.values[i]
                offer[i] = min(self.counts[i], int(needed) + 1)
                current_value += offer[i] * self.values[i]
        
        return offer
    
    def should_accept(self, offer_value: int) -> bool:
        """Determine if we should accept the opponent's offer."""
        # Calculate how many turns are left
        total_turns = self.max_rounds * 2
        
        # If this is the last possible turn, accept any positive offer
        if self.turn_count >= total_turns:
            return offer_value > 0
        
        # Calculate the minimum acceptable value based on remaining turns
        # As deadline approaches, we become more willing to accept
        progress = (self.turn_count - 1) / total_turns
        min_acceptable = self.total_value * (0.45 + 0.2 * progress)
        
        return offer_value >= min_acceptable
    
    def make_counter_offer(self, opponent_offer: list[int], opponent_offer_value: int) -> list[int]:
        """Make a counter-offer based on the opponent's offer."""
        # Start with our previous offer (or initial offer if first counter)
        if self.my_offers:
            counter_offer = self.my_offers[-1].copy()
        else:
            counter_offer = self.make_initial_offer()
        
        # Calculate how many rounds have elapsed
        rounds_elapsed = (self.turn_count + 1) // 2
        
        # Be patient - only concede if we're close to deadline or opponent isn't progressing
        if rounds_elapsed < self.max_rounds // 2:
            # Check if the opponent's offer has improved since last time
            if len(self.opponent_offers) > 1:
                prev_our_share = self.calculate_opponent_share(self.opponent_offers[-2])
                prev_offer_value = self.calculate_value(prev_our_share)
                # If the opponent's offer has improved, don't concede yet
                if opponent_offer_value > prev_offer_value:
                    return counter_offer
            # Otherwise, stick with our offer
            return counter_offer
        
        # We're close to the deadline, start conceding one item per round
        for i in reversed(self.item_priority):
            if counter_offer[i] > 0:
                counter_offer[i] -= 1
                break
        
        return counter_offer