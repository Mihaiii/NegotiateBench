class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turns_elapsed = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        # Sort indices by value to prioritize high-value items
        self.indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            # Check how much the partner offered US
            received_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Logic:
            # We become more lenient as the deadline approaches.
            # max_rounds * 2 is the absolute turn limit.
            # If the partner is second (me=0), the 2nd player has the last word.
            remaining_turns = self.total_turns - self.turns_elapsed
            
            # Calculate threshold based on time remaining
            if remaining_turns <= 1:
                threshold = 1  # Last chance: take anything better than 0
            elif remaining_turns <= 3:
                threshold = self.total_value * 0.4
            elif remaining_turns <= self.total_turns * 0.2:
                threshold = self.total_value * 0.6
            else:
                threshold = self.total_value * 0.8
            
            if received_val >= max(threshold, 1):
                return None
            
            self.turns_elapsed += 1 # Increment for the partner's turn

        # Counter-offer Logic
        # Progress goes from 0 to 1
        progress = self.turns_elapsed / self.total_turns
        
        # Target high value early, and lower it gradually
        if progress < 0.3:
            target_ratio = 1.0
        elif progress < 0.6:
            target_ratio = 0.9
        elif progress < 0.8:
            target_ratio = 0.7
        else:
            target_ratio = 0.5
            
        my_offer = self._build_offer(target_ratio)
        self.turns_elapsed += 1
        return my_offer

    def _build_offer(self, target_ratio: float) -> list[int]:
        target_val = target_ratio * self.total_value
        offer = [0] * len(self.counts)
        current_val = 0
        
        # Priority 1: Take all items that are valuable to us
        for i in self.indices:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val + self.values[i] <= target_val:
                        offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # Priority 2: Ensure we don't offer an empty hand if we have value
        if current_val == 0 and self.total_value > 0:
            offer[self.indices[0]] = 1
            current_val += self.values[self.indices[0]]

        # Priority 3: Leave some "useless" items (to us) for the partner to facilitate a deal
        # If we are asking for everything, give back the least valuable items to us
        if sum(offer) == sum(self.counts):
            for i in reversed(self.indices):
                if offer[i] > 0:
                    offer[i] -= 1
                    break
        
        return offer