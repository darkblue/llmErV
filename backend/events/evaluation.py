def error_rate(reference, hypothesis, unit='character'):
    """Levenshtein WER/CER; caller supplies authorized reference data."""
    a, b = (reference.split(), hypothesis.split()) if unit == 'word' else (list(reference), list(hypothesis))
    if not a: raise ValueError('reference must not be empty')
    row = list(range(len(b)+1))
    for i, x in enumerate(a,1):
        new = [i]
        for j,y in enumerate(b,1): new.append(min(new[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=new
    return row[-1]/len(a)
