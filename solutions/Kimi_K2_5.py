class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = list(counts)
        self.values = list(values)
        self.n = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_turns = max_rounds * 2
        self.turn = 0
        
        # Initialize opponent values as equal to my values
        self.opp_values = [float(v) for v in values]
        
    def offer(self, o):
        # Convert offer to integers if present
        if o is not None:
            o = [int(x) for x in o]
            
        remaining = self.total_turns - self.turn
        is_last = (remaining == 1)
        
        # Process opponent offer
        if o is not None:
            self._update_model(o)
            offer_val = sum(a * b for a, b in zip(o, self.values))
            
            if self._should_accept(offer_val, is_last, remaining):
                self.turn += 1
                return None
        
        # Generate counter-offer
        my_offer = self._create_offer(is_last, remaining)
        self.turn += 1
        return my_offer
    
    def _update_model(self, o):
        """Update opponent value estimates based on what they offered"""
        alpha = 0.35
        
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
                
            given = o[i]
            kept = self.counts[i] - given
            
            if given == self.counts[i]:
                # Gave all away - likely worthless to them
                self.opp_values[i] *= (1 - alpha * 0.6)
            elif kept == self.counts[i]:
                # Kept all - very valuable
                inferred = max(self.values[i] * 1.3, self.opp_values[i] * 1.1)
                self.opp_values[i] = self.opp_values[i] * (1 - alpha) + inferred * alpha
            else:
                # Partial - value proportional to amount kept
                ratio = kept / self.counts[i]
                # If they keep most, they value it higher
                scale = 0.5 + 1.5 * ratio  # 0.5 to 2.0
                inferred = self.opp_values[i] * scale
                self.opp_values[i] = self.opp_values[i] * (1 - alpha) + inferred * alpha
            
            self.opp_values[i] = max(0.0, self.opp_values[i])
    
    def _should_accept(self, offer_val, is_last, remaining):
        """Acceptance logic with dynamic thresholds"""
        if is_last:
            return offer_val > 0
            
        progress = self.turn / (self.total_turns - 1) if self.total_turns > 1 else 0
        
        # Threshold starts at 75%, drops to 40%
        threshold = self.total_value * (0.75 - 0.35 * progress)
        
        if offer_val >= threshold:
            return True
            
        # Accept if decent offer and running out of time
        if remaining <= 2 and offer_val >= self.total_value * 0.35:
            return True
            
        return False
    
    def _create_offer(self, is_last, remaining):
        """Generate offer based on current target and opponent model"""
        progress = self.turn / (self.total_turns - 1) if self.total_turns > 1 else 0
        
        # Target value: 80% -> 50% over time, 50% on last turn
        if is_last:
            target = self.total_value * 0.5
        else:
            target = self.total_value * (0.80 - 0.30 * progress)
        
        # Sort items by net value: my_value - 0.5 * opponent_estimate
        # Prioritize items valuable to me, not valuable to opponent
        items = []
        for i in range(self.n):
            my_val = self.values[i]
            opp_val = self.opp_values[i]
            score = my_val - 0.5 * opp_val
            items.append((score, my_val, i))
        
        items.sort(reverse=True)
        
        take = [0] * self.n
        current = 0
        
        for score, my_val, i in items:
            if current >= target:
                break
            if my_val <= 0:
                continue
            
            # Calculate needed units
            need_val = target - current
            units = int((need_val + my_val - 1) // my_val)
            actual = min(units, self.counts[i])
            
            take[i] = actual
            current += actual * my_val
        
        return take