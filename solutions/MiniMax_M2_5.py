class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        
        # Track which turn we're on (0 = first turn, then increments after each of our offers)
        self.my_turn_num = 0
        # Track total offers made by both sides
        self.offer_count = 0
        
    def _value(self, alloc: list[int]) -> int:
        """Compute my value for an allocation."""
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def _get_target_share(self) -> float:
        """Target share we aim for, declining as time runs out."""
        # Start aiming for ~52% and decline to ~40% by the end
        progress = min(1.0, self.my_turn_num / max(1, self.max_rounds * 2 - 1))
        return 0.52 - progress * 0.12
    
    def _get_min_accept(self) -> float:
        """Minimum value we'll accept, declining as time runs out."""
        # Start at 48% and decline to 35% as time runs out
        progress = min(1.0, self.my_turn_num / max(1, self.max_rounds * 2 - 1))
        return 0.48 - progress * 0.13
    
    def _make_offer(self, target_share: float) -> list[int]:
        """Create an offer targeting a specific share of total value."""
        # Start with all items
        offer = self.counts.copy()
        target = self.total * target_share
        
        # Remove items starting from lowest value to maximize what we keep
        # We want to keep high-value items and give away low-value ones
        while self._value(offer) > target and sum(offer) > 0:
            # Find item with lowest value per unit that we have > 0
            best_idx = -1
            best_value = float('inf')
            for i in range(len(offer)):
                if offer[i] > 0 and self.values[i] < best_value:
                    best_value = self.values[i]
                    best_idx = i
            
            if best_idx >= 0:
                offer[best_idx] -= 1
            else:
                break
        
        # Ensure we don't ask for nothing if we can get something
        if self._value(offer) == 0 and sum(self.counts) > 0:
            # Take one item of highest value
            best_idx = max(range(len(self.values)), key=lambda i: self.values[i])
            if self.values[best_idx] > 0:
                offer[best_idx] = min(1, self.counts[best_idx])
        
        return offer
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        # Increment offer count
        self.offer_count += 1
        
        # First turn: o is None (no offer received)
        if o is None:
            # If I'm second (me=1), this is still my turn to make an offer
            # I just haven't received one yet
            if self.me == 1 and self.offer_count == 1:
                # First turn and I'm second - make an initial offer
                target = self._get_target_share()
                return self._make_offer(target)
            
            # First turn and I'm first - make initial offer
            if self.me == 0 and self.offer_count == 1:
                target = self._get_target_share()
                return self._make_offer(target)
            
            # This shouldn't happen in normal flow, but handle gracefully
            return self._make_offer(0.45)
        
        # Received an offer from partner - check if we should accept
        offer_value = self._value(o)
        min_accept = self.total * self._get_min_accept()
        
        # Accept if offer is good enough
        if offer_value >= min_accept:
            return None  # Accept the offer
        
        # Make counter-offer
        self.my_turn_num += 1
        target = self._get_target_share()
        return self._make_offer(target)