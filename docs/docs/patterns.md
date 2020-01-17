---
id: patterns
title: Patterns
---

Here are the patterns the tool recognises, and how to fix them.

## Enumeration

### Slow Duplicate Checking

(Pattern name: `overlapChecking`)

You are using a slow way of duplicate checking between 2 lists.
Use [this](https://stackoverflow.com/a/17735466) instead.

## String Manipulation

### Joining

(Pattern name: `plusEquals`)

Joining strings can be very slow, even when the strings are small.

#### Slow Joining Examples

```python
mystring += "other string"
```

```python
string = string1 + string2
```

#### Fast Joining Examples

```python
myvar = 2

string = "some variable: %s" % str(myvar)
```

```python
myname = "Reece"
mylastname = "Dunham"

# .join is way faster then a lot of methods commonly used!
myfullname = " ".join([myname, mylastname])
```
