import random
import math
from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        # Calculate total value
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Generate all possible allocations for yourself (0 to counts[i] inclusive)
        self.all_allocations = self._generate_allocations()
        
        # Calculate my value for each allocation
        self.my_values = [self._calculate_value(alloc) for alloc in self.all_allocations]
        
        # Sort allocations by my value (descending)
        self.sorted_indices = sorted(range(len(self.my_values)), 
                                    key=lambda i: self.my_values[i], reverse=True)
        
        # Track state
        self.current_round = 0
        self.opponent_offers = [] if me == 0 else [None]  # Start with None if going second
        
        # Parameters for concession strategy
        self.reservation_value = self.total_value * 0.7  # Minimum acceptable value
        self.target_value = self.total_value * 0.85  # Initial target
        self.concession_rate = 0.9  # How fast we concede
        
        # Cache for utility calculations
        self.best_allocations = []
        
    def _generate_allocations(self) -> List[List[int]]:
        """Generate all possible allocations for yourself"""
        allocations = [[]]
        for count in self.counts:
            new_allocations = []
            for alloc in allocations:
                for i in range(count + 1):
                    new_allocations.append(alloc + [i])
            allocations = new_allocations
        return allocations
    
    def _calculate_value(self, allocation: List[int]) -> int:
        """Calculate my value for a given allocation"""
        return sum(v * a for v, a in zip(self.values, allocation))
    
    def _calculate_partner_value(self, allocation: List[int]) -> int:
        """Calculate what's left for partner (total - my value)"""
        return self.total_value - self._calculate_value(allocation)
    
    def _is_valid_allocation(self, allocation: List[int]) -> bool:
        """Check if allocation is valid (0 <= amount <= count for each type)"""
        return all(0 <= a <= c for a, c in zip(allocation, self.counts))
    
    def _get_best_allocations(self, min_my_value: int = 0) -> List[List[int]]:
        """Get allocations where my value >= min_my_value, sorted by partner value (descending)"""
        candidates = []
        for i in self.sorted_indices:
            if self.my_values[i] < min_my_value:
                break
            partner_value = self._calculate_partner_value(self.all_allocations[i])
            candidates.append((self.my_values[i], partner_value, self.all_allocations[i]))
        
        # Sort by my value descending, then partner value descending
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [alloc for _, _, alloc in candidates]
    
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """Make or accept an offer"""
        self.current_round += 1
        
        # Store opponent's offer
        if o is not None:
            self.opponent_offers.append(o)
        
        # Calculate my value from opponent's offer
        if o is not None:
            opponent_offer_value = self._calculate_value(o)
        else:
            opponent_offer_value = 0
        
        # Adjust target based on round progress
        progress = min(1.0, self.current_round / (self.max_rounds * 2))
        current_target = self.target_value * (1 - progress * (1 - self.concession_rate))
        current_target = max(current_target, self.reservation_value)
        
        # If opponent's offer is good enough, accept
        if o is not None and opponent_offer_value >= current_target:
            return None
        
        # If last round and opponent's offer gives me something, accept
        if self.current_round >= self.max_rounds * 2 and o is not None and opponent_offer_value > 0:
            return None
        
        # Generate counter-offer
        # Start with high-value allocations and gradually concede
        if progress < 0.3:
            # Early rounds: aim high
            min_value = int(current_target * 1.1)
        elif progress < 0.7:
            # Middle rounds: moderate demands
            min_value = int(current_target)
        else:
            # Late rounds: be more flexible but maintain minimum
            min_value = int(self.reservation_value)
        
        # Get best allocations meeting our minimum
        best_allocations = self._get_best_allocations(min_value)
        
        if best_allocations:
            # If we have opponent's previous offers, try to find allocation they might accept
            if self.opponent_offers:
                # Try to find allocation that gives partner reasonable value
                # (assuming partner wants at least some value)
                partner_target = self.total_value - min_value
                for alloc in best_allocations:
                    partner_value = self._calculate_partner_value(alloc)
                    if partner_value >= partner_target * 0.6:  # Partner gets at least 60% of what's left
                        return alloc
            # Return the best allocation for us
            return best_allocations[0]
        else:
            # No allocation meets minimum, fallback to best possible
            return self.all_allocations[self.sorted_indices[0]]