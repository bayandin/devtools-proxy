#  DevTools Proxy

## Usage
```
python3 devtools-proxy.py
```

## How it works

```
                          +---+
+----------+              |   |
| CLIENT 1 +<-----WS----->+ D |
+----------+              | E |
                          | V |
+----------+              | T |
| CLIENT 2 +<-----WS----->+ O |
+----------+              | O |              +--------+
                          | L +<-----WS----->+ CHROME |
                          | S |              +--------+
                          |   |
                          | P |
                          | R |
                          | O |
+----------+              | X |
| CLIENT N +<-----WS----->+ Y |
+----------+              |   |
                          +---+

```
