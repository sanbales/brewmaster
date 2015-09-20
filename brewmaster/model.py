from __future__ import division, print_function
from json import load
from random import expovariate, normalvariate, sample
import simpy
from util import SimpyMixin, poisson, csv_to_dict, json_to_dict


DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
DEFAULT_HOURS = {'Monday': [10, 22],
                 'Tuesday': [10, 22],
                 'Wednesday': [10, 22],
                 'Thursday': [10, 22],
                 'Friday': [10, 24],
                 'Saturday': [9, 24],
                 'Sunday': [12, 20]}
MAX_MASH_WAIT = 6
AVG_GROUP_ARRIVAL_TIME = 0.5
AVG_GROUP_SIZE = 4
AVG_GROUP_STAY = 1.5
AVG_NUM_DRINKS = 1.2
KEGS_PER_PINT = 1 / 124
GALLONS_PER_KEG = 15.5
TIME_TO_DELIVER = [5, 48]
MAX_AMOUNT_PER_INGREDIENT = 100


def check_inputs(beers, prices):
    for beer, data in beers.items():
        if beer not in prices:
            raise KeyError('Beer {} is not listed in prices'.format(beer))
        for ingredient in data['ingredients']:
            if ingredient not in prices:
                raise KeyError('Ingredient {} for beer {} is not listed in prices'.format(ingredient, beer))


class Keg(SimpyMixin):
    def __init__(self, name=None, expiration=0, init=0, *args, **kwargs):
        super(Keg, self).__init__(*args, **kwargs)
        expiration = 24 * expiration
        self.expiration = self.now + expiration if expiration < self.now else expiration
        self.name = name
        self.contents = self.new_container(capacity=124, init=init)
        self.clean = True

        amount = self.contents.level
        get = self.contents.get

    def fill(self, beer, amount=None):
        if amount is None:
            amount = self.contents.capacity
        if amount > self.contents.capacity:
            raise ValueError("Keg has capacity of {}, cannot fill it with {} pints of beer".format(self.contents.capacity, amount))
        self.name = beer
        self.clean = False
        self.contents.put(amount)


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

        except simpy.Interrupt:
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


class Brewery(SimpyMixin):
    def __init__(self, beers_list='beers.json',
                 price_list='prices.csv',
                 initial_funds=10000.0,
                 num_mash_tuns=1,
                 num_fermenters=1,
                 num_cooper_tanks=1,
                 max_barley=1000,
                 max_hops=1000,
                 num_bar_kegs=5,
                 num_stored_kegs=10,
                 batch_size=2,
                 hours=None, *args, **kwargs):

        super(Brewery, self).__init__(*args, **kwargs)

        self.register = self.new_container(init=initial_funds)
        self.beers = {name: beer for name, beer in json_to_dict(beers_list).items()}
        for beer in self.beers:
            self.beers[beer].update({'name': beer})
        self.prices = {item['name']: item['price'] for item in csv_to_dict(price_list)}
        self.hours = hours if hours is not None else DEFAULT_HOURS
        self.batch_size = batch_size

        self.patrons = []

        self.mash_tuns = self.new_resource(capacity=num_mash_tuns)
        self.cooper_tanks = self.new_resource(capacity=num_cooper_tanks)
        self.fermenters = self.new_store(capacity=num_fermenters)

        self.dry_storage = {}
        for ingredient in [beer['ingredients'] for beer in self.beers.values()][0]:
            if ingredient not in self.dry_storage:
                self.dry_storage[ingredient] = self.new_container(init=1000)
        self.cellar = self.new_store(capacity=num_stored_kegs, kind='filter')
        self.tapped_kegs = self.new_store(capacity=num_bar_kegs, kind='filter')

        for _ in range(num_stored_kegs):
            self.cellar.put(Keg())

        check_inputs(self.beers, self.prices)
        self.buying_ingredients = self.process(self.buy_ingredients())
        #self.running_bar = self.process(self.run_bar())
        self.running_brewery = self.process(self.run_brewery())

        self.errors = None

    def buy_ingredients(self):
        while True:
            yield self.wait(1)
            for ingredient, container in self.dry_storage.items():
                if container.level == 0:
                    quantity = MAX_AMOUNT_PER_INGREDIENT / self.prices[ingredient]
                    self.buy_ingredient(ingredient, quantity)

    def buy_ingredient(self, ingredient, quantity):
        # Await arrival of ingredient
        yield self.wait(TIME_TO_DELIVER)
        # Stock ingredient
        self.dry_storage[ingredient] += quantity
        # Pay for ingredient
        self.register -= self.prices[ingredient] * quantity

    def run_bar(self):
        idx = 0
        while True:
            start, end = self.hours[DAYS[idx]]
            time_till_open = max(0, start - self.now % 24.0)
            yield self.wait(time_till_open)
            self.log("Brewery is open")
            self.serving = self.process(self.serve_customers())
            time_till_close = max(0, end - self.now % 24.0)
            yield self.wait(time_till_close)
            self.serving.interrupt("Brewery is closing")
            self.log("Brewery is closing")
            idx = (idx + 1) % 7

    def serve_customers(self):
        while True:
            try:
                self.wait(expovariate(AVG_GROUP_ARRIVAL_TIME))
                self.patrons.append(Patron(brewery=self))
            except simpy.Interrupt:
                self.log("Kicking out {} patrons".format(len(self.patrons)))
                for patron in patrons:
                    patron.consuming.interrupt()
                    del patron
                self.patrons = []

    def order(self, beers, pints):
        if hasattr(beers, __iter__):
            if isinstance(pints, (int, float)):
                for beer in beers:
                    yield self.register.put(self.sell(beer, pints))
            else:
                for beer, pints_of_beer in zip(beers, pints):
                    yield self.register.put(self.sell(beer, pints_of_beer))
        else:
            yield self.register(self.sell(beer, pints))

    def find_keg(self, beer, location='bar', any_beer=False):
        if location == 'bar':
            storage = self.tapped_kegs.items
        elif location == 'cellar':
            storage = self.cellar.items
        kegs = sorted([keg for keg in storage if keg.name == beer], key=lambda x: x.level)
        if kegs:
            return kegs[0]
        return None

    def swap_keg(self, keg):
        old_keg = yield self.tapped_kegs.get(filter=lambda x: x == keg)
        new_keg = find_keg(keg.name, location='cellar')
        if new_keg is None:
            tapped_kegs = [item.name for item in self.tapped_kegs.items]
            new_keg = yield self.cellar.get(filter=lambda x: x.name not in tapped_kegs)
        if new_keg is None:
            new_keg = yield self.cellar.get()
        yield self.tapped_kegs.put(new_keg)
        old_keg.name = None
        yield self.cellar.put(old_keg)

    def pour(self, beer, pints):
        keg = self.find_keg(beer)

        if keg.contents.level < pints:
            poured = keg.contents.level
        else:
            poured = pints

        yield keg.get(poured)

        if poured < pints:
            self.swap_keg(keg)
            poured += self.pour(beer, pints - poured)
            if poured < pints:
                self.log('Failed to sell {} pints of {}'.format(pints - poured, beer))
        yield poured

    def sell(self, beer, pints):
        poured = self.pour(beer, pints)
        return poured * self.prices[beer]

    def inventory(self, beer):
        return sum(keg.amount for keg in self.cellar.items if keg.name == beer) + \
               sum(keg.amount for keg in self.tapped_kegs.items if keg.name == beer)

    def run_brewery(self):
        while True:
            kegs = []
            while len(kegs) < self.batch_size:
                with self.cellar.get(filter=lambda keg: keg.clean) as req:
                    keg = yield req
                    kegs.append(keg)

            beer = self.select_beer_to_brew()

            if beer is None:
                yield self.wait(2)
                continue

            kegs = yield self.process(self.brew_beer(self.beers[beer], kegs))

            for keg in kegs[num_kegs:]:
                yield self.cellar.put(keg)

    def select_beer_to_brew(self):
        candidates = [beer for beer, recipe in self.beers.items() if all(self.dry_storage[ingredient].level >= recipe['ingredients'][ingredient] * self.batch_size for ingredient in recipe['ingredients'])]
        if candidates:
            return sorted(candidates, key=lambda beer: self.inventory(beer))[0]
        else:
            return None

    def brew_beer(self, beer, kegs):
        """
        Simulates the brewing process for a beer and fills the kegs given.

        :param beer: the beer to brew
        :param kegs: the list of kegs to fill once the beer is brewed

        :type beer: dict
        :type kegs: list
        """
        if isinstance(beer, basestring):
            beer = self.beers[beer]

        quantity = len(kegs)
        ingredients = {}
        for ingredient in beer['ingredients']:
            ingredients[ingredient] = self.dry_storage[ingredient].get(beer[ingredient] * quantity)

        mash_tun = self.mash_tuns.request()
        request = yield mash_tun | self.wait(MAX_START_WAIT)
        if mash_tun in request:
            yield self.wait(beer['mash_time'])

        fermenter = self.fermenters.request()
        request = yield fermenter | self.wait(MAX_MASH_WAIT)
        if fermenter in request.events:
            self.mash_tuns.release(mash_tun)
            self.log("Released Mash Tun for beer " + beer['name'])
            self.log("Starting fermentation for beer " + beer['name'])
            yield self.wait(beer['fermentation_time'])
            self.log("Finished fermentation for beer " + beer['name'])
        else:
            self.mash_tuns.release(mash_tun)
            self.log("Failed batch of {} ({} kegs) because of timeout for fermenter".format(beer['name'], quantity))
            yield kegs

        self.log("Starting conditioning for beer " + beer['name'])
        conditioner = self.conditioners.request()
        start_conditioning = self.now
        conditioning_time = uniform(beer['conditioning_time'])
        request = yield conditioner | self.wait(conditioning_time)
        if conditioner in request.events:
            self.fermenters.release(fermenter)
            self.log("Finished conditioning for beer " + beer['name'])
            self.wait(conditioning_time - (self.now - start_conditioning))
        else:
            self.fermenters.release(fermenter)
            self.conditioners.release(conditioner)

        # TODO: find formula for number of kegs made
        num_kegs = self.batch_size
        yield self.wait(self.time_to_keg * num_kegs)

        amount_brewed = 124 * num_kegs

        for keg in kegs[:num_kegs]:
            keg.fill(beer['name'])

        yield kegs

'''
2.      Availability of hops.  This is handled by contract and we have a reasonably good hanld on this at the moment.  However, we'd certainly like to be able to use whatever is developed to project hops for future contracts.

Cold side of brewing is fermentation.  For the purpose of  the model, we will consider time in the fermenters rather than time in fermentation.  Fermentation is a finite length of time where beer could be left in the fermenters for an indefinite period.
1.       Beer is place into the fermenter on brew day and shortly begins fermentation.

2.       Fermentation time is a variable that is relatively constant based on yeast.

3.      Once fermentation is complete, there is a conditioning phase that can be estimated but will have greater variability than fermentation time.

4.      Once conditioning is complete, the beer can be moved to storage, but may also be allowed to stay in the fermenter.

Storage provides the most variability as it can be affected by many things:
        Consumption rates which we can provide based on our 4 plus months of sales

        Cooperage which could be increased. We'd like to be able to show value of cooperage purchase based on simulation

        Distribution.  We'd like to be able to make gains with distribution not only by selling beer, but by strategically selling beer that will help our upstream production.

        Distribution also includes festival participation that can drain stock.  We'd like to be able to use the tool to set limits on festival participation.

'''
