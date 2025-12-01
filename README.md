Running tests and the application.

```
pip install -r requirements-dev.txt
```

Run tests
```
pytest
```

Run the program
```
python -m project.main input.txt 1 1 1 1 1 1 1 1
```

Changes from proposal
```
- Admissable heuristic
- DFS but pick the leaf with the lowest bounding score
```