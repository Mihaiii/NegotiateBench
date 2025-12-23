# -*- coding: utf-8 -*-
"""
A robust haggling negotiation agent.

The agent
* guarantees the classic sub‑game‑perfect safety target,
* builds a tiny opponent model from the items the opponent keeps,
* constructs counter‑offers that respect the guarantee while giving the
  opponent the items it seems to value most.
"""

from typing import List, Optional


class Agent:
    def __init__(
        self,
        me: int,
        counts: List[int],
        values: List[int],
        max_rounds: int,
    ) -> None:
        # problem data -------------------------------------------------
        self.counts = counts[:]          # total amount of each type
        self.values = values[:]          # our per‑item values
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # negotiation state --------------------------------------------
        # number of *full* rounds (two moves) still possible
        self.rounds_left = max_rounds

        # base order: most valuable for us first (stable)
        self.base_order = sorted(
            range(self.n),
            key=lambda i: self.values[i],
            reverse=True,
        )

        # opponent model – how many of each type the opponent has kept
        self.opp_keep = [0] * self.n
        self.opp_offers_seen = 0

    # --------------------------------------------------------------- #
    def _value(self, bundle: List[int]) -> int:
        """Our valuation of a bundle."""
        return sum(b * v for b, v in zip(bundle, self.values))

    # --------------------------------------------------------------- #
    def _target(self) -> int:
        """
        Minimal value we are willing to accept given the remaining rounds.

        With r rounds left the safe guarantee is ceil(total / (r+1)).
        When r == 0 we accept any final offer.
        """
        r = self.rounds_left
        if r <= 0:
            return 0
        # ceil division
        return (self.total + r) // (r + 1)

    # --------------------------------------------------------------- #
    def _update_opp_model(self, offer: List[int]) -> None:
        """
        Record the items the opponent kept in his last offer.

        `offer` is what *we* would receive, therefore the opponent keeps
        `counts[i] - offer[i]` pieces of type i.
        """
        for i in range(self.n):
            self.opp_keep[i] += self.counts[i] - offer[i]
        self.opp_offers_seen += 1

    # --------------------------------------------------------------- #
    def _order_for_us(self) -> List[int]:
        """
        Order of types to consider when we *pick* items for ourselves.

        We prefer high our‑value *and* low opponent‑keep count.
        """
        if self.opp_offers_seen == 0:
            return self.base_order[:]

        # sort by (-our value, opponent keep) => high value, low keep first
        return sorted(
            range(self.n),
            key=lambda i: (-self.values[i], self.opp_keep[i])
        )

    # --------------------------------------------------------------- #
    def _favored_order_for_opp(self) -> List[int]:
        """
        Order of types the opponent seems to like most.

        Higher `opp_keep` → higher assumed opponent value.
        """
        if self.opp_offers_seen == 0:
            return self.base_order[:]

        return sorted(
            range(self.n),
            key=lambda i: self.opp_keep[i],
            reverse=True,
        )

    # --------------------------------------------------------------- #
    def _make_counter(self) -> List[int]:
        """
        Build a safe and opponent‑friendly counter‑offer.

        1. Take the cheapest set of items that reaches the safety target,
           preferring types the opponent values little.
        2. If we have slack (we could give away more without falling below
           the target) we willingly hand over items the opponent likes most.
        """
        target = self._target()
        allocation = [0] * self.n          # items we keep

        # ---------- Phase 1 – satisfy the guarantee -----------------
        order = self._order_for_us()
        remaining = target

        for i in order:
            if remaining <= 0:
                break
            val = self.values[i]
            if val == 0:
                continue
            available = self.counts[i]
            # how many of this type are needed (ceil division)
            need = (remaining + val - 1) // val
            take = min(available, need)
            allocation[i] = take
            remaining -= take * val

        # If we couldn't hit the target (only zero‑value items left),
        # just take everything – it never hurts the guarantee.
        if remaining > 0:
            return self.counts[:]

        # ---------- Phase 2 – give opponent what it likes -------------
        # Current value of our allocation
        cur_val = self._value(allocation)

        # Try to drop items that the opponent cares about, as long as we stay safe
        opp_fav = self._favored_order_for_opp()
        for i in opp_fav:
            while allocation[i] > 0 and cur_val - self.values[i] >= target:
                allocation[i] -= 1
                cur_val -= self.values[i]

        return allocation

    # --------------------------------------------------------------- #
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called on each of our turns.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last offer expressed as the bundle we would
            receive. ``None`` for the very first turn when we move first.

        Returns
        -------
        list[int] | None
            * ``None`` – we accept the opponent's offer.
            * list[int] – our counter‑offer (the bundle we would receive).
        """
        # If we received an offer, a full round has elapsed.
        if o is not None:
            self.rounds_left -= 1
            self._update_opp_model(o)

            # Accept if the offer meets our safety target.
            if self._value(o) >= self._target():
                return None

            # Otherwise propose a new safe offer.
            return self._make_counter()

        # No offer → we are the first mover of a new round.
        return self._make_counter()