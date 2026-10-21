# Small MapReduce word counter

**Name:** Jack Ashraf  
**Student ID:** 231006166

Run with Python 3. No packages to install, no Hadoop, and no Spark.

```powershell
python mapreduce.py
```

Or choose the folders:

```powershell
python mapreduce.py input output
```

The five original text files are included in `input/`. The program produces
`output/reducer_0.txt` and `output/reducer_1.txt`, with one `word<TAB>count`
per line. Each output is alphabetically sorted. Running again overwrites these
two output files.

## How to explain it in the discussion

1. **Split:** each `.txt` file directly inside the input folder is one split.
2. **Map:** one thread per split emits `(word, 1)` for every word. All threads
   start before the program waits for them. Words are lowercase English letter
   sequences; punctuation and numbers are separators.
3. **Combine:** each mapper uses its own dictionary to calculate local subtotals.
   For example, three occurrences of `data` become `(data, 3)`.
4. **Partition:** add the character codes in the word and take the remainder
   after division by 2. This chooses reducer 0 or 1. The same word always goes
   to the same reducer, including when it comes from different files.
5. **Shuffle and sort:** collect each reducer's pairs from every mapper, sort
   them by word, then explicitly group their counts into lists.
6. **Reduce:** loop over each word's list of counts, add them, and write the
   total to that reducer's output file.

Example with two input splits:

```text
Split A: Data data big
Split B: Big data

Map A: (data, 1), (data, 1), (big, 1)
Map B: (big, 1), (data, 1)

Combine A: (data, 2), (big, 1)
Combine B: (big, 1), (data, 1)

Partition: data -> reducer 0; big -> reducer 0
Shuffle and sort: big -> [1, 1]; data -> [2, 1]
Reduce: big -> 2; data -> 3
```

Both example words happen to choose reducer 0. Reducer 1 still gets its own
output file, even when its partition is empty. For comparison, `a` chooses
reducer 1.

The grouping and counting are written explicitly in `combine`,
`shuffle_and_sort`, and `reduce_words`. Python's sort only orders pairs; it
does not count or group them. Reducers run sequentially; the assignment's
mapper concurrency is implemented with threads. Threads allow concurrent file
reading, but Python's GIL limits parallel execution of CPU work. Intermediate
results stay in memory, which is suitable for this small educational dataset.

## Dataset

Source: [Big-Data-Analytics text dataset](https://github.com/dr-ahmed-said/Big-Data-Analytics/tree/main/datasets/text-files).
The original dataset instructions and expected counts are in `reference/`,
outside the input folder so the reference answer is never counted as input.

**Reference discrepancy:** the repository's supplied `expected_word_count.txt`
does not match its five books. The actual books contain **235 words and 182
unique words**; the supplied reference totals 225 words. For example, `data`
appears twice but the reference lists 1, and `analysis` appears twice but is
missing from the reference. The original reference is preserved unchanged.
