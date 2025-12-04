### Running the program
#### Small inputs
```
python -m project.main input.txt 1 1 1 1 1 1 1 1
```
#### Large inputs
Add one more flag (ex. True) to indicate large inputs and return the first valid solution instead of most optimal. 
```
python -m project.main input.txt 1 1 1 1 1 1 1 1 True
```

### Run tests
```
# create a venv
python -m venv .venv
source .venv/bin/activate
# install deps
pip install -r requirements-dev.txt
```

```
pytest
```