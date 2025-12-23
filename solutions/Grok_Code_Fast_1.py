from itertools import product

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.rounds = self.total_turns
        self.index = 0
        # Generate all possible splits (what I get), sorted by my value descending
        ranges = [range(count + 1) for count in counts]
        self.splits = []
        for split in product(*ranges):
            v = sum(split[i] * values[i] for i in range(len(split)))
            self.splits.append((list(split), v))
        self.splits.sort(key=lambda x: x[1], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds = max(self.rounds - 1, 0)
        if o is not None:
            # Partner offered o; calculate value to me
            offered_v = sum(o[i] * self.values[i] for i in range(len(o)))
            # Threshold: start at 0.5 * total, decrease to 0
            progress = 1 - (self.rounds / self.total_turns) if self.total_turns > 0 else 1
            threshold = self.total * (0.5 - 0.5 * progress)
            if offered_v >= threshold:
                return None  # Accept
            
            # If not accepted and it's my turn to counter, offer more generous split
            # Increase index to move to a lower-value split for me (conceding)
            self.index = min(self.index + 1, len(self.splits) - 1)
            return self.splits[self.index][0]
        else:
            # First offer: propose the highest value split for me
            return self.splits[self.index][0]