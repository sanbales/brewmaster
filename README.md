# brewmaster
A model-based framework to assist breweries in optimizing their processes.

# Install
You can pip install the package using this command:

```
pip install git+git://github.com/sanbales/brewmaster.git
```

or install a specific version by using this command:

```
pip install git+git://github.com/sanbales/brewmaster.git#<version>
```

where <version> is the semantic version, e.g., 0.0.1

# Usage
You can run the model by simply typing:

```
from brewmaster.brewery import Brewery

brewery = Brewery()  # Make a brewery with default parameters

brewery.run()        # Run the simulation for a year
```
