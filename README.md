# iblrigv8

Welcome to the International Brain Laboratory decision making task implementation.

The task is implemented in the Bpod system (Sanworks) and uses the Bonsai visual programming language (on Windows) for the visual stimuli and Python for all other purposes.


## Documentation and installation steps here:
https://int-brain-lab.github.io/iblrig



### Run tests locally
```shell
flake8
python -m unittest discover ./iblrig/test
```

### Build the documentation
```shell
# make sure pre-requisites are installed
pip install --upgrade -e .[DEV]
# create the static directory
rm -rf ./docs/build
mkdir -p ./docs/build/html/_static
# unit tests generate task diagrams
python -m unittest discover ./iblrig/test
# generate class diagrams
pyreverse -o png -m y --ignore iblrig.test -A --output-directory ./docs/build/html/_static ./iblrig_tasks
# build and serve the docs locally
sphinx-autobuild ./docs/source ./docs/build/html/
```
