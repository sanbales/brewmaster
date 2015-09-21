from __future__ import division, print_function
from random import expovariate, sample
from util import Interrupt, SimpyMixin, poisson, csv_to_dict, json_to_dict


AVG_GROUP_SIZE = 4
AVG_GROUP_STAY = 1.5
AVG_NUM_DRINKS = 1.2


class Patron(SimpyMixin):
    def __init__(self, brewery, *args, **kwargs):
        super(Patron, self).__init__(*args, **kwargs)
        self.brewery = brewery
        self.departure = self.now + expovariate(AVG_GROUP_STAY)
        self.party_size = poisson(AVG_GROUP_SIZE - 1) + 1
        self.order = [poisson(AVG_NUM_DRINKS) for _ in range(self.party_size)]
        self.name = "Party of {} arrived at {:10}".format(self.party_size, self.now)
        self.consuming = self.process(self.consume())

    def consume(self):
        try:
            self.log(self.name + ' arrived')
            yield self.wait(TIME_TO_BE_SEATED)
            self.log(self.name + ' waiting to order')
            yield self.wait(TIME_TO_ORDER)
            beers = self.select_beers()
            self.brewery.buy(beers, 1)
            self.log(self.name + ' waiting to be served')
            yield self.wait(TIME_TO_BE_SERVED)

        except Interrupt:
            self.log('party {} leaving {} hrs early'.format(self.departure - now))

    def select_beers(self):
        beers = []
        for customer in range(self.party_size):
            other_beer = None
            beer = sample(brewery.beers, 1)
            name = beer['name']
            if name not in brewery.kegs or brewery.kegs[name].level < KEGS_PER_PINT:
                other_beer = sample([key for key, keg in brewery.kegs.items() if keg.level > KEGS_PER_PINT], 1)
                self.log('customer in party {} could get {} so they ordered {}'.format(self.name, name, new_beer))
            if other_beer is None:
                beers.append(beer)
            else:
                beers.append(other_beer)

        return beers
