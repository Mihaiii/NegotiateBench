import itertools
import math
from typing import List

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_left = max_rounds
        self.num_types = len(counts)
        
        # Calculate total value for me
        self.total_value = sum(counts[i] * values[i] for i in range(self.num_types))
        
        # Generate all possible allocations I could receive
        self.generate_all_allocations()
        
        # Sort allocations by my value (descending)
        self.allocations.sort(key=lambda x: self.calc_my_value(x), reverse=True)
        
        # Target value - start high, decrease over time
        self.min_acceptable = self.total_value * 0.7  # Start wanting 70%
        self.concession_rate = 0.9  # How much to reduce target each round
        
        # Track opponent's offers to infer their preferences
        self.opponent_offers = []
        
    def generate_all_allocations(self):
        """Generate all possible allocations I could receive"""
        ranges = [range(count + 1) for count in self.counts]
        self.allocations = list(itertools.product(*ranges))
    
    def calc_my_value(self, allocation):
        """Calculate my value for a given allocation"""
        return sum(allocation[i] * self.values[i] for i in range(self.num_types))
    
    def calc_partner_value(self, allocation, partner_values=None):
        """Calculate partner's value for what they would get"""
        if partner_values is None:
            # Assume partner values inversely to me (worst case)
            partner_values = [1 if v == 0 else 0 for v in self.values]
        
        partner_allocation = [self.counts[i] - allocation[i] for i in range(self.num_types)]
        return sum(partner_allocation[i] * partner_values[i] for i in range(self.num_types))
    
    def is_valid_allocation(self, allocation):
        """Check if allocation doesn't exceed available items"""
        return all(0 <= allocation[i] <= self.counts[i] for i in range(self.num_types))
    
    def find_best_offer(self, target_value):
        """Find the best offer for me that gives at least target_value"""
        for alloc in self.allocations:
            my_val = self.calc_my_value(alloc)
            if my_val >= target_value:
                # Check if this might be acceptable to opponent
                # Try to give opponent items I don't value much
                partner_val = self.calc_partner_value(alloc)
                if partner_val > 0:  # Partner gets something
                    return list(alloc)
        # Fallback: take everything I value
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.num_types)]
    
    def offer(self, o: List[int] | None) -> List[int] | None:
        self.rounds_left -= 0.5  # Each offer is half a round
        
        # If this is the first offer and I go first
        if o is None and self.me == 0:
            # Start with a strong but reasonable offer
            target = self.total_value * 0.8
            return self.find_best_offer(target)
        
        # If opponent made an offer
        if o is not None:
            # Calculate value of opponent's offer
            offer_value = self.calc_my_value(o)
            
            # Store opponent's offer for pattern analysis
            self.opponent_offers.append(o)
            
            # Adjust target based on remaining rounds
            time_pressure = self.rounds_left / self.max_rounds
            current_target = max(self.total_value * 0.5, 
                               self.min_acceptable * (time_pressure ** 0.5))
            
            # Accept if offer meets current target
            if offer_value >= current_target:
                return None
            
            # If we're in the last round, be more lenient
            if self.rounds_left <= 1:
                last_chance_target = self.total_value * 0.4
                if offer_value >= last_chance_target:
                    return None
        
        # Make a counter-offer
        # Adjust target downward as rounds progress
        time_factor = (self.max_rounds - self.rounds_left) / self.max_rounds
        concession = 1.0 - (time_factor * self.concession_rate)
        current_target = self.total_value * max(0.5, concession)
        
        # Find an offer that gives me current_target value
        counter_offer = self.find_best_offer(current_target)
        
        # If we're running out of time, make a more generous offer
        if self.rounds_left <= 2:
            # Try to find a win-win allocation
            for alloc in self.allocations:
                my_val = self.calc_my_value(alloc)
                # In last rounds, accept lower value but ensure partner gets something
                if my_val >= self.total_value * 0.4:
                    partner_val = self.calc_partner_value(alloc)
                    if partner_val >= self.total_value * 0.3:  # Partner gets reasonable value
                        return list(alloc)
        
        return counter_offer