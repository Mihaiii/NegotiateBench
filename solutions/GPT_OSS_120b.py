# -*- coding: utf-8 -*-
"""
Deterministic bargaining agent.

The strategy (explained above) never walks away, always returns a
legal allocation and runs in O(N log N) per turn.
"""

from typing import List, Optional


class Agent:
    def __init__(self, me: int, counts: List[int],
                 values: List[int], max_rounds: int) -> None:
        """
        Parameters
        ----------
        me : int
            0 if we move first, 1 otherwise (not used – strategy is symmetric).
        counts : list[int]
            Number of objects of each type.
        values : list[int]
            Our value for a single object of each type.
        max_rounds : int
            Maximum number of *rounds* (a round = two turns).
        """
        # store immutable copies
        self.counts = counts[:]
        self.values = values[:]
        self.max_rounds = max_rounds

        # total value of all items (identical for opponent)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # total number of turns we will ever be asked to act
        self.remaining_turns = max_rounds * 2

    # -----------------------------------------------------------------
    # Helper utilities
    # -----------------------------------------------------------------
    def _value_of(self, share: List[int]) -> int:
        """Value of a given share according to our valuations."""
        return sum(v * q for v, q in zip(self.values, share))

    def _max_fraction_allowed(self) -> float:
        """
        Fraction of any item type we may keep in the current turn.
        It linearly decays to 0 when the deadline is reached.
        The denominator (2*max_rounds + 1) provides a tiny slack that
        prevents division‑by‑zero on the very last turn.
        """
        return self.remaining_turns / (self.max_rounds * 2 + 1)

    def _greedy_limits(self, max_frac: float) -> List[int]:
        """Maximum number of each item type we could keep under `max_frac`."""
        return [int(max_frac * c) for c in self.counts]

    def _best_future_value(self, max_frac: float) -> int:
        """
        Upper bound on the value we could still achieve if we respect the
        current `max_frac`.  It is obtained by taking, in descending order
        of our per‑item value, as many items as the limits allow.
        """
        limits = self._greedy_limits(max_frac)
        # sort indices by value descending
        order = sorted(range(len(self.values)),
                       key=lambda i: self.values[i],
                       reverse=True)
        value = 0
        for i in order:
            value += self.values[i] * limits[i]
        return value

    # -----------------------------------------------------------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called on each of our turns.

        Parameters
        ----------
        o : list[int] | None
            Opponent's last proposal (what we would receive).  ``None`` on
            the very first turn.

        Returns
        -------
        list[int] | None
            * ``None`` – we accept the opponent's proposal.
            * list[int] – our counter‑proposal (how many of each type we want).
        """
        # a turn is consumed
        self.remaining_turns -= 1

        # -------------------------------------------------------------
        # 1)  Possibly accept the opponent's offer
        # -------------------------------------------------------------
        if o is not None:
            my_val = self._value_of(o)

            # optimistic bound on what we could still get later
            max_frac = self._max_fraction_allowed()
            future_best = self._best_future_value(max_frac)

            # accept if the offer is at least as good as the bound
            if my_val >= future_best:
                return None

            # safety net: accept any “fair” split (≥ half of total)
            if my_val >= self.total * 0.5:
                return None

        # -------------------------------------------------------------
        # 2)  Build a counter‑proposal
        # -------------------------------------------------------------
        n = len(self.counts)

        # If this is our very last turn we concede everything.
        if self.remaining_turns == 0:
            return [0] * n

        max_frac = self._max_fraction_allowed()
        limits = self._greedy_limits(max_frac)

        # Greedy allocation: take as many high‑valued items as allowed.
        order = sorted(range(n), key=lambda i: self.values[i], reverse=True)
        share = [0] * n
        for i in order:
            share[i] = limits[i]

        return share