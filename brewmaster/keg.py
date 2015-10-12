from __future__ import division, print_function
from .util import SimpyMixin


KEGS_PER_PINT = 1 / 124
GALLONS_PER_KEG = 15.5


class Keg(SimpyMixin):
    def __init__(self, name=None, expiration=0, init=0, *args, **kwargs):
        super(Keg, self).__init__(*args, **kwargs)
        expiration = 24 * expiration
        self.expiration = self.now + expiration if expiration < self.now else expiration
        self.name = name
        self.contents = self.new_container(capacity=124, init=init)
        self.clean = True

        get = self.contents.get

    @property
    def amount(self):
        return self.contents.level

    def fill(self, beer, amount=None):
        if amount is None:
            amount = self.contents.capacity
        if amount > self.contents.capacity:
            raise ValueError("Keg has capacity of {}, cannot fill it with {} pints of beer".format(self.contents.capacity, amount))
        self.name = beer
        self.clean = False
        self.contents.put(amount)

    def empty(self):
        self.get(self.amount)
