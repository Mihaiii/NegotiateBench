class Agent:
    """
    A negotiation agent that uses a time-based concession strategy.
    
    The agent:
    1. Starts by demanding all items it values > 0 (ignores zero-value items)
    2. Accepts offers meeting a threshold that decreases from 70% to 10% of total value
    3. Concedes items in order: zero-value items first, then by increasing personal value
    4. Makes one concession per turn where opponent's offer is rejected
    """
    
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        # Total value of all items to us
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Turn counter
        self.turn = 0
        
        # Initial demand: claim all items we value positively
        self.current_offer = [counts[i] if values[i] > 0 else 0 
                             for i in range(len(counts))]
        
        # Concession order: by increasing our valuation, then by decreasing count
        self.concession_order = sorted(
            range(len(counts)),
            key=lambda i: (values[i], -counts[i])
        )
    
    def _value(self, offer: list[int]) -> int:
        """Calculate value of an offer to us"""
        if offer is None:
            return 0
        return sum(v * a for v, a in zip(self.values, offer))
    
    def _validate(self, offer: list[int]) -> list[int]:
        """Ensure offer is valid (0 <= offer[i] <= counts[i])"""
        return [min(max(0, offer[i]), self.counts[i]) for i in range(len(self.counts))]
    
    def _turns_left(self) -> int:
        """Calculate turns remaining in negotiation"""
        return max(0, self.max_rounds * 2 - self.turn)
    
    def _should_accept(self, opp_offer: list[int]) -> bool:
        """Accept if offer meets time-decreasing threshold (70% → 10%)"""
        if self.total_value == 0:  # Everything is worthless
            return True
        
        value = self._value(opp_offer)
        
        if value >= self.total_value:  # Perfect offer
            return True
        
        if self._turns_left() <= 1:  # Last turn: accept anything
            return True
        
        # Threshold linearly decreases with progress
        progress = self.turn / (self.max_rounds * 2)
        threshold = self.total_value * (0.7 - 0.6 * progress)
        
        return value >= int(threshold + 0.5)
    
    def _concede(self) -> None:
        """Make one minimal concession: give away zero-value items or one unit of lowest-value item"""
        # First pass: give away all zero-value items
        for i, val in enumerate(self.values):
            if val == 0 and self.current_offer[i] > 0:
                self.current_offer[i] = 0
                return
        
        # Second pass: give one unit of least valuable item
        for i in self.concession_order:
            if self.current_offer[i] > 0:
                self.current_offer[i] -= 1
                return
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        """Main negotiation turn: accept or make counter-offer"""
        self.turn += 1
        
        if o is not None:  # Opponent made an offer
            opp_offer = self._validate(o)
            
            if self._should_accept(opp_offer):
                return None  # Accept
            
            # Reject and make a concession
            self._concede()
        
        # Return our (possibly conceded) offer
        return self._validate(self.current_offer)