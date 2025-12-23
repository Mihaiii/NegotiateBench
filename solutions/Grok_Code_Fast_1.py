from itertools import product

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.rounds = self.max_rounds * 2
        self.index = 0
        # Generate all possible splits (what I get), sorted by my value descending
        ranges = [range(count + 1) for count in counts]
        self.splits = []
        for split in product(*ranges):
            v = sum(split[i] * values[i] for i in range(len(split)))
            self.splits.append((list(split), v))
        self.splits.sort(key=lambda x: x[1], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is None:
            # First offer: propose the highest value split for me
            return self.splits[0][0]
        else:
            # Partner offered o; calculate value to me
            offered_v = sum(o[i] * self.values[i] for i in range(len(o)))
            # Threshold decreases as rounds left decrease
            rounds_left = max(self.rounds, 1)  # avoid division by zero, use at least 1
            threshold = self.total * (rounds_left / (self.max_rounds * 2))
            if offered_v >= threshold:
                return None  # Accept
            else:
                # Offer next split in the list (more generous)
                self.index = min(self.index + 1, len(self.splits) - 1)
                return self.splits[self.index][0]