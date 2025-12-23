class Agent:
    """
    Negotiation agent for the haggling problem.

    Parameters
    ----------
    me : int
        0 if we move first, 1 otherwise (not used in the strategy).
    counts : list[int]
        Number of objects of each type.
    values : list[int]
        Our per‑object value for each type (non‑negative integers).
    max_rounds : int
        Maximum number of *rounds* (a round = two turns).
    """

    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts[:]          # total objects
        self.values = values[:]          # our values
        self.max_rounds = max_rounds

        # total value of the whole basket according to us
        self.total_value = sum(c * v for c, v in zip(counts, values))

        # safe target value we will never accept less than
        # ceil(total / (max_rounds + 1))
        self.target = (self.total_value + max_rounds) // (max_rounds + 1)

        # pre‑compute the order in which we prefer items (high value first)
        self.order = sorted(
            range(len(counts)),
            key=lambda i: self.values[i],
            reverse=True,
        )

    # --------------------------------------------------------------------- #
    def _value_of(self, bundle: list[int]) -> int:
        """Utility – compute our valuation of a given bundle."""
        return sum(b * v for b, v in zip(bundle, self.values))

    # --------------------------------------------------------------------- #
    def _make_counter(self) -> list[int]:
        """
        Build a counter‑offer that gives us at least `self.target` value.
        Greedily take the most valuable items until the target is met.
        """
        remaining_target = self.target
        allocation = [0] * len(self.counts)

        for i in self.order:
            if remaining_target <= 0:
                break
            per_item = self.values[i]
            if per_item == 0:
                continue          # never helps us reach the target
            available = self.counts[i]

            # Minimum items needed from this type to cover the remaining target
            need = (remaining_target + per_item - 1) // per_item  # ceil division
            take = min(available, need)

            allocation[i] = take
            remaining_target -= take * per_item

        # If after the loop we still haven't reached the target (possible only
        # when all remaining items have zero value), just take everything we
        # can – it does not hurt the guarantee because the target is already
        # the maximal reachable value in that situation.
        if remaining_target > 0:
            for i in range(len(self.counts)):
                allocation[i] = self.counts[i]

        return allocation

    # --------------------------------------------------------------------- #
    def offer(self, o: list[int] | None) -> list[int] | None:
        """
        Called each time it is our turn.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last offer expressed as the bundle we would receive.
            `None` for the very first turn when we move first.

        Returns
        -------
        list[int] | None
            * `None` – we accept the opponent's offer.
            * list[int] – our counter‑offer (the bundle we would receive).
        """
        # If we received an offer, decide whether to accept it.
        if o is not None:
            if self._value_of(o) >= self.target:
                # Accept – return None.
                return None

        # Otherwise we must propose a split.
        return self._make_counter()