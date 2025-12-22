from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        self.num_types = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_number = 0
        
        # Negotiation state
        self.current_offer = None
        self.last_opp_offer = None
        self.opp_repeats = 0
        
        # Acceptance threshold (high initially)
        self.accept_threshold = self.total_value * 0.85
        
        # Stubbornness: concessions only after opponent repeats this many times
        self.stubbornness = 3
    
    def _our_value(self, offer: List[int]) -> int:
        """Calculate value of an offer according to our valuation"""
        return sum(v * a for v, a in zip(self.values, offer))
    
    def _turns_remaining(self) -> int:
        """Calculate turns left in negotiation"""
        return self.max_rounds * 2 - self.turn_number
    
    def _should_accept(self, offer: List[int]) -> bool:
        """Determine if we should accept opponent's offer"""
        if self.total_value == 0:
            return True
        
        value = self._our_value(offer)
        turns_left = self._turns_remaining()
        
        # Become more flexible as deadline approaches
        if turns_left <= 2:
            return value >= self.total_value * 0.25
        if turns_left <= 5:
            return value >= self.total_value * 0.45
        
        return value >= self.accept_threshold
    
    def _make_initial_offer(self) -> List[int]:
        """Maximalist: ask for all items"""
        return self.counts[:]
    
    def _make_concession(self) -> List[int]:
        """Create a new offer with minimal concession"""
        if self.current_offer is None:
            return self._make_initial_offer()
        
        offer = self.current_offer[:]
        
        # First, give away all items worth 0 to us
        for i, val in enumerate(self.values):
            if val == 0 and offer[i] > 0:
                offer[i] = 0
                return offer
        
        # Then give away one unit of the lowest-value item we have
        sorted_indices = sorted(range(self.num_types), key=lambda i: self.values[i])
        for i in sorted_indices:
            if offer[i] > 0:
                offer[i] -= 1
                return offer
        
        return offer
    
    def _validate_offer(self, offer: List[int]) -> List[int]:
        """Ensure offer is valid (doesn't exceed available items)"""
        return [min(offer[i], self.counts[i]) for i in range(self.num_types)]
    
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """Main negotiation entry point - called each turn"""
        self.turn_number += 1
        
        # Process opponent's offer if provided
        if o is not None:
            # Track opponent offer repetitions
            if self.last_opp_offer is not None and o == self.last_opp_offer:
                self.opp_repeats += 1
            else:
                self.opp_repeats = 1
                self.last_opp_offer = o[:]
            
            # Accept if offer is good enough
            if self._should_accept(o):
                return None
        
        # Generate our offer
        
        # First turn: ask for everything
        if self.current_offer is None:
            self.current_offer = self._make_initial_offer()
            return self._validate_offer(self.current_offer)
        
        # Adjust patience based on remaining time
        turns_left = self._turns_remaining()
        if turns_left <= 5:
            self.stubbornness = 2  # Be less patient near deadline
        
        # Concede only if opponent is being stubborn
        if self.opp_repeats >= self.stubbornness:
            self.current_offer = self._make_concession()
            self.opp_repeats = 0
        
        return self._validate_offer(self.current_offer)